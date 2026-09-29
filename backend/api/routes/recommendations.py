from fastapi import APIRouter, HTTPException

from backend.api.deps import CurrentUser, Session
from backend.schemas.recommendations import RecommendationRequest, RecommendationResponse
from backend.services import recommendations as recommendation_service

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post("", response_model=RecommendationResponse)
async def recommend(request: RecommendationRequest, user: CurrentUser, session: Session) -> RecommendationResponse:
    try:
        return await recommendation_service.recommend(session, user_id=user.user_id, request=request)
    except recommendation_service.ScrapNotFound as error:
        # 다른 사용자의 스크랩도 존재 여부를 드러내지 않도록 같은 404로 응답한다.
        raise HTTPException(status_code=404, detail=f"Scrap not found: {error.scrap_ids}") from None
