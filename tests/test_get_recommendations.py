import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError

from backend.clients import ollama_client
from backend.db.session import get_session
from backend.main import app
from backend.repositories import recommendations as repository
from backend.schemas.recommendations import FitResult, PlaceRecommendationQuery, RecommendedPlace
from backend.services import recommendations as service


class FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return self.rows


class OllamaClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_format_is_only_sent_when_requested(self):
        payloads = []

        def respond(request):
            payloads.append(json.loads(request.content))
            return httpx.Response(200, json={"message": {"content": "{}"}})

        original_client = httpx.AsyncClient

        def test_client(*args, **kwargs):
            return original_client(*args, transport=httpx.MockTransport(respond), **kwargs)

        settings = SimpleNamespace(ollama_base_url="http://test", ollama_timeout_seconds=5)
        with (
            patch.object(ollama_client, "get_settings", return_value=settings),
            patch.object(ollama_client.httpx, "AsyncClient", side_effect=test_client),
        ):
            await ollama_client.OllamaClient().chat("test-model", [])
            await ollama_client.OllamaClient().chat("test-model", [], format={"type": "object"})
        self.assertNotIn("format", payloads[0])
        self.assertEqual(payloads[1]["format"], {"type": "object"})


class RepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_category_uses_category_table_and_region_relation(self):
        session = FakeSession([(31, "해동용궁사", "attraction", "haeundae")])
        candidates = await repository.recommendation_candidates(
            session, category="attraction", after_id=0, batch_size=12,
        )
        sql = str(session.statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
        self.assertEqual(candidates[0].place_id, 31)
        self.assertIn("JOIN place_categories", sql)
        self.assertIn("JOIN districts", sql)
        self.assertIn("JOIN regions", sql)
        self.assertIn("category_code = 'attraction'", sql)
        self.assertIn("LIMIT 12", sql)

    async def test_reviews_are_partitioned_by_place_and_exclude_synthetic(self):
        session = FakeSession([(31, 101, "바다가 보여요"), (32, 201, "조용해요")])
        reviews = await repository.candidate_reviews(session, [31, 32], per_place=3)
        sql = str(session.statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
        self.assertEqual(reviews, {31: {101: "바다가 보여요"}, 32: {201: "조용해요"}})
        self.assertIn("PARTITION BY reviews.place_id", sql)
        self.assertIn("reviews.is_synthetic IS false", sql)
        self.assertIn("review_rank <= 3", sql)
        self.assertIn("reviews.review_id", sql)


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.place_a = repository.PlaceCandidate(31, "뮤지엄 원", "attraction", "haeundae")
        self.place_b = repository.PlaceCandidate(32, "고릴라브루잉", "restaurant", "gwangan")
        self.place_c = repository.PlaceCandidate(33, "요트클럽", "attraction", "haeundae")
        # a: 걷기·계단 모두 편함, b: 아이 동반 편함(부모님 관련 aspect 없음), c: 걷기 힘듦
        self.counts = [
            (31, "walking_burden", "positive", 8), (31, "slope_stairs", "positive", 6),
            (32, "family_friendly", "positive", 8), (32, "food_quality", "positive", 5),
            (33, "walking_burden", "negative", 8),
        ]
        self.text_a = "미술관의 전시가 좋았습니다. " + "관람하기 편했습니다. " * 50

    async def recommend(self, query, *, model="test-model", client=None, reviews=None):
        client = client or SimpleNamespace(chat=AsyncMock(return_value='{"reason":"리뷰 근거 이유"}'))
        with (
            patch.object(repository, "recommendation_candidates",
                         new=AsyncMock(side_effect=[[self.place_a, self.place_b, self.place_c], []])) as candidates,
            patch.object(repository, "sentiment_counts", new=AsyncMock(return_value=self.counts)),
            patch.object(repository, "review_counts", new=AsyncMock(return_value={31: 10, 32: 10, 33: 10})),
            patch.object(repository, "candidate_reviews", new=AsyncMock(return_value=reviews or {
                31: {101: self.text_a}, 32: {201: "아이와 점심 먹기 좋았어요"},
            })),
            patch.object(service, "get_settings", return_value=SimpleNamespace(ollama_model=model)),
        ):
            results = await service.recommend_places(object(), query, client)
        return results, candidates, client

    def test_condition_weights_reuse_keyword_rules_once(self):
        self.assertEqual(service.condition_weights(PlaceRecommendationQuery(walk="low", avoids=["stairs"])),
                         {"walking_burden": 4, "slope_stairs": 4})
        self.assertEqual(service.condition_weights(PlaceRecommendationQuery(priorities=["quiet"], avoids=["noise"])),
                         {"noise_level": 3.5})
        self.assertEqual(service.condition_weights(PlaceRecommendationQuery(priorities=["culture"], walk="ok")), {})

    async def test_parents_and_kids_rank_differently(self):
        parents, candidates, _ = await self.recommend(PlaceRecommendationQuery(companion="parents", category="attraction"))
        kids, _, _ = await self.recommend(PlaceRecommendationQuery(companion="kids"))
        self.assertEqual(candidates.await_args_list[0].kwargs["category"], "attraction")
        # 부모님: b는 관련 aspect가 없어 제외, c는 걷기 부담이 커서 40 미만으로 제외
        self.assertEqual([(r.place.place_id, r.fit) for r in parents], [(31, 88.8)])
        self.assertEqual([(r.place.place_id, r.fit) for r in kids], [(32, 90.0), (31, 88.8)])

    async def test_no_conditions_uses_overall_satisfaction_and_limit(self):
        results, _, _ = await self.recommend(PlaceRecommendationQuery(limit=1))
        self.assertEqual([r.place.place_id for r in results], [31])

    async def test_model_only_writes_reason_for_selected_place(self):
        results, _, client = await self.recommend(PlaceRecommendationQuery(companion="parents"))
        self.assertEqual(results[0].reason, "리뷰 근거 이유")
        self.assertEqual(results[0].strengths, [])
        call = client.chat.await_args_list[0]
        payload = json.loads(call.args[1][1]["content"])
        self.assertEqual(client.chat.await_count, 1)
        self.assertEqual(payload["place"]["place_id"], 31)
        self.assertEqual(payload["reviews"], [{"review_id": 101, "review_text": self.text_a}])
        self.assertIn("reason", call.kwargs["format"]["properties"])

    async def test_reason_falls_back_to_labels_without_model(self):
        for kwargs in (
            {"model": None},
            {"client": SimpleNamespace(chat=AsyncMock(return_value="not json"))},
            {"client": SimpleNamespace(chat=AsyncMock(side_effect=httpx.ConnectError("offline")))},
        ):
            with self.subTest(kwargs=kwargs):
                results, _, _ = await self.recommend(PlaceRecommendationQuery(companion="parents"), **kwargs)
                self.assertEqual([r.place.place_id for r in results], [31])
                self.assertEqual(results[0].reason, "요구사항과 관련해 걷기 부담, 경사·계단 평가가 좋아요.")

    async def test_all_below_threshold_returns_empty(self):
        self.counts = [(31, "walking_burden", "negative", 8)]
        results, _, client = await self.recommend(PlaceRecommendationQuery(companion="parents"))
        self.assertEqual(results, [])
        client.chat.assert_not_awaited()


class RouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        async def fake_session():
            yield object()
        app.dependency_overrides[get_session] = fake_session
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        app.dependency_overrides.clear()

    async def test_anonymous_get_and_existing_post_auth(self):
        with patch.object(service, "recommend_places", new=AsyncMock(return_value=[])) as recommend:
            get = await self.client.get("/api/v1/recommendations", params={"with": "parents", "pri": "sea,quiet", "limit": 2})
            post = await self.client.post("/api/v1/recommendations", json={"scrap_ids": [1], "requirements": "바다"})
        self.assertEqual(get.status_code, 200)
        self.assertEqual(get.json(), [])
        self.assertEqual(post.status_code, 401)
        query = recommend.await_args.args[1]
        self.assertEqual(query.companion, "parents")
        self.assertEqual(query.priorities, ["sea", "quiet"])
        self.assertEqual(query.limit, 2)

    async def test_invalid_conditions(self):
        for params in ({"category": "invalid"}, {"pri": "sea,unknown"}, {"limit": 51}, {"walk": "invalid"}):
            with self.subTest(params=params):
                response = await self.client.get("/api/v1/recommendations", params=params)
                self.assertEqual(response.status_code, 422)

    async def test_fit_result_matches_frontend_shape(self):
        result = FitResult(
            place=RecommendedPlace(place_id=31, name="해동용궁사", category="attraction", region="haeundae"),
            fit=78, reason="바다가 보인다는 리뷰가 있어요.", strengths=[], cautions=[],
        )
        with patch.object(service, "recommend_places", new=AsyncMock(return_value=[result])):
            response = await self.client.get("/api/v1/recommendations")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{
            "place": {"place_id": 31, "name": "해동용궁사", "category": "attraction", "region": "haeundae"},
            "fit": 78.0, "reason": "바다가 보인다는 리뷰가 있어요.", "strengths": [], "cautions": [],
        }])

    async def test_database_error_is_http_error(self):
        for error, status in (
            (SQLAlchemyError("offline"), 503),
        ):
            with self.subTest(error=error):
                with patch.object(service, "recommend_places", new=AsyncMock(side_effect=error)):
                    response = await self.client.get("/api/v1/recommendations")
                self.assertEqual(response.status_code, status)
