from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["hotel", "restaurant", "attraction"]
ModelId = Literal["base", "lora", "qlora"]


class AnalyzeRequest(BaseModel):
    review: str = Field(min_length=1, max_length=2000)
    category: Category
    model: ModelId = "qlora"


class AspectResult(BaseModel):
    category: str  # aspect 이름 (예: photo_spots)
    attribute: str
    sentiment: Literal["positive", "negative", "neutral"]
    evidence: str


class AnalysisResult(BaseModel):
    traveler_context: list[str]
    aspects: list[AspectResult]
