from dataclasses import dataclass

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.annotation import ReviewAnnotation
from backend.models.aspect import Aspect
from backend.models.catalog import District, PlaceCategory, Region
from backend.models.place import Place
from backend.models.review import Review
from backend.models.scrap import Scrap


@dataclass(frozen=True)
class PlaceCandidate:
    place_id: int
    name: str
    category: str
    region: str


async def recommendation_candidates(
    session: AsyncSession, *, category: str | None, after_id: int, batch_size: int,
) -> list[PlaceCandidate]:
    """프론트가 표시할 수 있는 장소를 ID 순서로 한 배치 조회한다."""
    query = (
        select(Place.place_id, Place.place_name, PlaceCategory.category_code, Region.region_code)
        .join(PlaceCategory, PlaceCategory.category_id == Place.category_id)
        .join(District, District.district_id == Place.district_id)
        .join(Region, Region.region_id == District.region_id)
        .where(
            Place.place_id > after_id,
            Place.place_name.is_not(None),
            PlaceCategory.category_code.in_(("hotel", "restaurant", "attraction")),
            Region.region_code.in_(("haeundae", "gwangan", "seomyeon", "wondo", "west")),
        )
        .order_by(Place.place_id)
        .limit(batch_size)
    )
    if category is not None:
        query = query.where(PlaceCategory.category_code == category)
    rows = await session.execute(query)
    return [PlaceCandidate(*row) for row in rows]


async def candidate_reviews(
    session: AsyncSession, place_ids: list[int], *, per_place: int,
) -> dict[int, dict[int, str]]:
    """장소마다 최신 실제 리뷰 몇 개의 ID와 원문을 함께 읽는다."""
    if not place_ids:
        return {}
    ranked = (
        select(
            Review.place_id.label("place_id"),
            Review.review_id.label("review_id"),
            Review.review_text.label("review_text"),
            func.row_number().over(
                partition_by=Review.place_id, order_by=Review.review_id.desc(),
            ).label("review_rank"),
        )
        .where(Review.place_id.in_(place_ids), Review.is_synthetic.is_(False))
        .subquery()
    )
    rows = await session.execute(
        select(ranked.c.place_id, ranked.c.review_id, ranked.c.review_text)
        .where(ranked.c.review_rank <= per_place)
        .order_by(ranked.c.place_id, ranked.c.review_rank)
    )
    reviews: dict[int, dict[int, str]] = {}
    for place_id, review_id, review_text in rows:
        if review_text.strip():
            reviews.setdefault(place_id, {})[review_id] = review_text
    return reviews


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
