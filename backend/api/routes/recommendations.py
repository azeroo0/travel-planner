from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from backend.api.deps import CurrentUser, Session
from backend.schemas.recommendations import (
    Category,
    Companion,
    FitResult,
    PlaceRecommendationQuery,
    RecommendationRequest,
    RecommendationResponse,
    Walk,
)
from backend.services import recommendations as recommendation_service

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

def _csv_values(raw: str | None, allowed: set[str]) -> list[str]:
    if raw is None:
        return []
    values = [value.strip() for value in raw.split(",")]
    if any(value not in allowed for value in values):
        raise HTTPException(status_code=422, detail="Invalid recommendation condition")
    return list(dict.fromkeys(values))


@router.get("", response_model=list[FitResult])
async def recommend_all(
    session: Session,
    companion: Annotated[Companion | None, Query(alias="with")] = None,
    walk: Walk | None = None,
    pri: Annotated[str | None, Query(max_length=100)] = None,
    avoid: Annotated[str | None, Query(max_length=100)] = None,
    category: Category | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[FitResult]:
    query = PlaceRecommendationQuery(
        companion=companion,
        walk=walk,
        priorities=_csv_values(pri, {"sea", "food", "photo", "culture", "rest", "quiet"}),
        avoids=_csv_values(avoid, {"waiting", "stairs", "noise", "parking", "crowd"}),
        category=category,
        limit=limit,
    )
    try:
        return await recommendation_service.recommend_places(session, query)
    except recommendation_service.PlaceModelUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    except recommendation_service.PlaceModelOutputInvalid as error:
        raise HTTPException(status_code=502, detail=str(error)) from None
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503, detail="Recommendation database is unavailable") from error


@router.post("", response_model=RecommendationResponse)
async def recommend(request: RecommendationRequest, user: CurrentUser, session: Session) -> RecommendationResponse:
    try:
        return await recommendation_service.recommend(session, user_id=user.user_id, request=request)
    except recommendation_service.ScrapNotFound as error:
        # 다른 사용자의 스크랩도 존재 여부를 드러내지 않도록 같은 404로 응답한다.
        raise HTTPException(status_code=404, detail=f"Scrap not found: {error.scrap_ids}") from None
