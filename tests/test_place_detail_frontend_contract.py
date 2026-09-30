import unittest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.session import get_session
from backend.main import app
from backend.models.catalog import District, PlaceCategory, Region
from backend.models.place import Place
from backend.models.place_assets import PlaceImage, PlaceTag, Tag
from backend.repositories import places as repository
from backend.services import places as service


class PlaceDetailFrontendContractTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection:
            await connection.run_sync(
                lambda sync_connection: Region.metadata.create_all(
                    sync_connection,
                    tables=[Region.__table__, District.__table__, PlaceCategory.__table__,
                            Place.__table__, PlaceImage.__table__, Tag.__table__, PlaceTag.__table__],
                )
            )
            await connection.execute(Region.__table__.insert(), {
                "region_id": 1, "region_code": "haeundae", "region_name": "해운대",
            })
            await connection.execute(District.__table__.insert(), {
                "district_id": 1, "region_id": 1, "district_name": "해운대구",
            })
            await connection.execute(PlaceCategory.__table__.insert(), {
                "category_id": 1, "category_code": "attraction", "category_name": "관광지",
            })
            await connection.execute(Place.__table__.insert(), {
                "place_id": 31, "category_id": 1, "district_id": 1,
                "source": "tripadvisor", "source_place_id": "31", "place_name": "뮤지엄 원",
                "address": "부산 해운대구", "latitude": Decimal("35.1234567"),
                "longitude": Decimal("129.1234567"), "intro_text": "디지털 전시를 볼 수 있는 곳",
                "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
            })
            await connection.execute(PlaceImage.__table__.insert(), [
                {"image_id": 1, "place_id": 31, "image_url": "https://example.com/side.jpg", "is_main": False, "sort_order": 0},
                {"image_id": 2, "place_id": 31, "image_url": "https://example.com/main.jpg", "is_main": True, "sort_order": 1},
            ])
            await connection.execute(Tag.__table__.insert(), {
                "tag_id": 1, "category": "theme", "tag_name": "전시",
            })
            await connection.execute(PlaceTag.__table__.insert(), {"place_id": 31, "tag_id": 1})
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

        async def test_session():
            async with self.sessions() as session:
                yield session

        app.dependency_overrides[get_session] = test_session

    async def asyncTearDown(self):
        app.dependency_overrides.clear()
        await self.engine.dispose()

    async def test_place_detail_has_fields_used_by_main_frontend(self):
        with patch.object(repository, "count_reviews", new=AsyncMock(return_value=3)):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/api/v1/places/31")
                missing = await client.get("/api/v1/places/999")
        self.assertEqual(response.status_code, 200)
        place = response.json()
        self.assertEqual(place["name"], "뮤지엄 원")
        self.assertEqual(place["category"], "attraction")
        self.assertEqual(place["region"], "haeundae")
        self.assertEqual(place["district"], "해운대구")
        self.assertEqual(place["summary"], "디지털 전시를 볼 수 있는 곳")
        self.assertEqual(place["review_count"], 3)
        self.assertEqual(place["main_image_url"], "https://example.com/main.jpg")
        self.assertEqual(place["images"][0]["image_url"], place["main_image_url"])
        self.assertEqual(place["tags"], [{"category": "theme", "tag_name": "전시"}])
        self.assertIsInstance(place["latitude"], float)
        self.assertEqual(missing.status_code, 404)

    async def test_evidence_context_is_display_text(self):
        with (
            patch.object(repository, "get_place", new=AsyncMock(return_value=object())),
            patch.object(repository, "evidence", new=AsyncMock(return_value=[
                (101, "원문 리뷰", "계단", "negative", 0, 2),
            ])),
            patch.object(repository, "review_contexts", new=AsyncMock(return_value={101: ["parents", "kids"]})),
        ):
            evidence = await service.get_evidence(
                object(), place_id=31, aspect="slope_stairs", sentiment="negative", context=None, limit=5,
            )
        self.assertEqual(evidence[0].context, "parents, kids")
        self.assertEqual(evidence[0].text, "원문 리뷰")
