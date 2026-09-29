from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    scrap_ids: list[int] = Field(min_length=1)
    requirements: str = Field(min_length=1)


class RecommendationResponse(BaseModel):
    detail: str
