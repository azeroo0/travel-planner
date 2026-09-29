from fastapi import APIRouter, HTTPException

from travel_planner.schemas.recommendations import RecommendationRequest, RecommendationResponse

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post("", status_code=501, response_model=RecommendationResponse)
async def recommend(request: RecommendationRequest) -> None:
    raise HTTPException(status_code=501, detail="Recommendations are not implemented")
