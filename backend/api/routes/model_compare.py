# [임시] 튜닝 전 원본 모델과 튜닝 모델의 추천 결과 비교. 비교가 끝나면 이 라우터를 지운다.
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from backend.api.deps import Session
from backend.api.routes.recommendations import _csv_values
from backend.schemas.recommendations import Category, Companion, PlaceRecommendationQuery, Walk
from backend.services import model_compare

router = APIRouter(prefix="/model-compare", tags=["model-compare"])


@router.get("/recommendations")
async def compare_recommendations(
    session: Session,
    companion: Annotated[Companion | None, Query(alias="with")] = None,
    walk: Walk | None = None,
    pri: Annotated[str | None, Query(max_length=100)] = None,
    avoid: Annotated[str | None, Query(max_length=100)] = None,
    category: Category | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[dict]:
    query = PlaceRecommendationQuery(
        companion=companion,
        walk=walk,
        priorities=_csv_values(pri, {"sea", "food", "photo", "culture", "rest", "quiet"}),
        avoids=_csv_values(avoid, {"waiting", "stairs", "noise", "parking", "crowd"}),
        category=category,
        limit=limit,
    )
    try:
        return await model_compare.compare(session, query)
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503, detail="Recommendation database is unavailable") from error
