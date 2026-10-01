from sqlalchemy import Select, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.annotation import ReviewAnnotation
from backend.models.aspect import Aspect
from backend.models.companion import CompanionType, ReviewCompanion
from backend.models.catalog import District, PlaceCategory, Region
from backend.models.place import Place
from backend.models.place_assets import PlaceImage, PlaceTag, Tag
from backend.models.review import Review


async def list_places(session: AsyncSession, *, limit: int, offset: int) -> list[Place]:
    result = await session.scalars(select(Place).order_by(Place.place_id).limit(limit).offset(offset))
    return list(result)


async def get_place(session: AsyncSession, place_id: int) -> Place | None:
    return await session.get(Place, place_id)


async def place_detail_info(session: AsyncSession, place_id: int) -> tuple[Place, str, str | None, str | None] | None:
    row = await session.execute(
        select(Place, PlaceCategory.category_code, District.district_name, Region.region_code)
        .join(PlaceCategory, PlaceCategory.category_id == Place.category_id)
        .outerjoin(District, District.district_id == Place.district_id)
        .outerjoin(Region, Region.region_id == District.region_id)
        .where(Place.place_id == place_id)
    )
    found = row.one_or_none()
    return tuple(found) if found else None


async def place_images(session: AsyncSession, place_id: int) -> list[PlaceImage]:
    rows = await session.scalars(
        select(PlaceImage).where(PlaceImage.place_id == place_id)
        .order_by(PlaceImage.is_main.desc(), PlaceImage.sort_order, PlaceImage.image_id)
    )
    return list(rows)


async def place_tags(session: AsyncSession, place_id: int) -> list[tuple[str | None, str]]:
    rows = await session.execute(
        select(Tag.category, Tag.tag_name)
        .join(PlaceTag, PlaceTag.tag_id == Tag.tag_id)
        .where(PlaceTag.place_id == place_id)
        .order_by(Tag.category, Tag.tag_name)
    )
    return [tuple(row) for row in rows]


async def count_reviews(session: AsyncSession, place_id: int) -> int:
    return await session.scalar(select(func.count()).select_from(Review).where(Review.place_id == place_id)) or 0


async def aspect_mentions(session: AsyncSession, place_id: int) -> list[tuple[str, str, int]]:
    """(aspect_name, sentiment, 언급한 리뷰 수). 한 리뷰가 같은 aspect를 여러 번 언급해도 1로 센다."""
    rows = await session.execute(
        select(Aspect.aspect_name, ReviewAnnotation.sentiment, func.count(distinct(ReviewAnnotation.review_id)))
        .join(Review, Review.review_id == ReviewAnnotation.review_id)
        .join(Aspect, Aspect.aspect_id == ReviewAnnotation.aspect_id)
        .where(Review.place_id == place_id)
        .group_by(Aspect.aspect_name, ReviewAnnotation.sentiment)
    )
    return [tuple(row) for row in rows]


async def context_counts(session: AsyncSession, place_id: int) -> list[tuple[str, int]]:
    rows = await session.execute(
        select(CompanionType.companion_code, func.count(distinct(ReviewCompanion.review_id)))
        .join(Review, Review.review_id == ReviewCompanion.review_id)
        .join(CompanionType, CompanionType.companion_type_id == ReviewCompanion.companion_type_id)
        .where(Review.place_id == place_id)
        .group_by(CompanionType.companion_code)
    )
    return [tuple(row) for row in rows]


async def context_sentiments(session: AsyncSession, place_id: int) -> list[tuple[str, str, int]]:
    """(동행 유형, sentiment, annotation 수)."""
    rows = await session.execute(
        select(CompanionType.companion_code, ReviewAnnotation.sentiment, func.count())
        .join(Review, Review.review_id == ReviewAnnotation.review_id)
        .join(ReviewCompanion, ReviewCompanion.review_id == Review.review_id)
        .join(CompanionType, CompanionType.companion_type_id == ReviewCompanion.companion_type_id)
        .where(Review.place_id == place_id)
        .group_by(CompanionType.companion_code, ReviewAnnotation.sentiment)
    )
    return [tuple(row) for row in rows]


def _evidence_query(place_id: int, aspect: str, sentiment: str | None, context: str | None) -> Select:
    query = (
        select(Review.review_id, Review.review_text, ReviewAnnotation.attribute_value, ReviewAnnotation.sentiment,
               ReviewAnnotation.evidence_start, ReviewAnnotation.evidence_end)
        .join(Review, Review.review_id == ReviewAnnotation.review_id)
        .join(Aspect, Aspect.aspect_id == ReviewAnnotation.aspect_id)
        .where(Review.place_id == place_id, Aspect.aspect_name == aspect)
    )
    if sentiment is not None:
        query = query.where(ReviewAnnotation.sentiment == sentiment)
    if context is not None:
        query = query.where(
            select(ReviewCompanion.review_id)
            .join(CompanionType, CompanionType.companion_type_id == ReviewCompanion.companion_type_id)
            .where(ReviewCompanion.review_id == Review.review_id, CompanionType.companion_code == context)
            .exists()
        )
    return query.order_by(Review.review_id, ReviewAnnotation.evidence_start)


async def evidence(
    session: AsyncSession, *, place_id: int, aspect: str, sentiment: str | None, context: str | None, limit: int,
) -> list[tuple]:
    rows = await session.execute(_evidence_query(place_id, aspect, sentiment, context).limit(limit))
    return [tuple(row) for row in rows]


async def review_contexts(session: AsyncSession, review_ids: list[int]) -> dict[int, list[str]]:
    if not review_ids:
        return {}
    rows = await session.execute(
        select(ReviewCompanion.review_id, CompanionType.companion_code)
        .join(CompanionType, CompanionType.companion_type_id == ReviewCompanion.companion_type_id)
        .where(ReviewCompanion.review_id.in_(review_ids))
        .order_by(ReviewCompanion.review_id, CompanionType.companion_code)
    )
    contexts: dict[int, list[str]] = {}
    for review_id, code in rows:
        contexts.setdefault(review_id, []).append(code)
    return contexts
