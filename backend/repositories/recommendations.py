from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.annotation import ReviewAnnotation
from backend.models.aspect import Aspect
from backend.models.catalog import PlaceCategory
from backend.models.place import Place
from backend.models.review import Review
from backend.models.scrap import Scrap


async def user_scraps(session: AsyncSession, *, user_id: int, scrap_ids: list[int]) -> list[Scrap]:
    result = await session.scalars(select(Scrap).where(Scrap.user_id == user_id, Scrap.scrap_id.in_(scrap_ids)))
    return list(result)


async def review_places(session: AsyncSession, review_ids: list[int]) -> dict[int, int]:
    if not review_ids:
        return {}
    rows = await session.execute(select(Review.review_id, Review.place_id).where(Review.review_id.in_(review_ids)))
    return dict(rows.tuples().all())


async def places(session: AsyncSession, place_ids: list[int]) -> dict[int, tuple[str | None, str]]:
    """place_id → (장소 이름, 카테고리 코드)."""
    rows = await session.execute(
        select(Place.place_id, Place.place_name, PlaceCategory.category_code)
        .join(PlaceCategory, PlaceCategory.category_id == Place.category_id)
        .where(Place.place_id.in_(place_ids))
    )
    return {place_id: (name, category) for place_id, name, category in rows}


async def review_counts(session: AsyncSession, place_ids: list[int]) -> dict[int, int]:
    rows = await session.execute(
        select(Review.place_id, func.count()).where(Review.place_id.in_(place_ids)).group_by(Review.place_id)
    )
    return dict(rows.tuples().all())


async def sentiment_counts(session: AsyncSession, place_ids: list[int]) -> list[tuple[int, str, str, int]]:
    """(place_id, aspect_name, sentiment, 라벨 수)."""
    rows = await session.execute(
        select(Review.place_id, Aspect.aspect_name, ReviewAnnotation.sentiment, func.count())
        .join(Review, Review.review_id == ReviewAnnotation.review_id)
        .join(Aspect, Aspect.aspect_id == ReviewAnnotation.aspect_id)
        .where(Review.place_id.in_(place_ids))
        .group_by(Review.place_id, Aspect.aspect_name, ReviewAnnotation.sentiment)
    )
    return [tuple(row) for row in rows]


async def evidence(session: AsyncSession, place_ids: list[int]) -> dict[tuple[int, str, str], str]:
    """(place_id, aspect, sentiment)별 대표 근거 문구 하나. Gold 라벨, 8자 이상 중 짧은 문구 순으로 고른다."""
    rows = await session.execute(
        select(Review.place_id, Aspect.aspect_name, ReviewAnnotation.sentiment, ReviewAnnotation.evidence_text)
        .join(Review, Review.review_id == ReviewAnnotation.review_id)
        .join(Aspect, Aspect.aspect_id == ReviewAnnotation.aspect_id)
        .where(Review.place_id.in_(place_ids))
        .distinct(Review.place_id, Aspect.aspect_name, ReviewAnnotation.sentiment)
        .order_by(
            Review.place_id, Aspect.aspect_name, ReviewAnnotation.sentiment,
            case((ReviewAnnotation.annotation_tier == "gold", 0), else_=1),
            case((func.length(ReviewAnnotation.evidence_text) < 8, 1), else_=0),  # "바닷바람"처럼 너무 짧은 문구는 뒤로
            func.length(ReviewAnnotation.evidence_text),
        )
    )
    return {(place_id, aspect, sentiment): text for place_id, aspect, sentiment, text in rows}
