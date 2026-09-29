from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    scrap_ids: list[int] = Field(min_length=1, max_length=50)
    requirements: str = Field(min_length=1, max_length=500)


class AspectWeight(BaseModel):
    aspect: str
    label: str
    weight: float
    keywords: list[str]  # 이 가중치를 만든 요구사항 속 키워드


class AspectScore(BaseModel):
    aspect: str
    label: str
    goodness: float  # 0~100, 50이 중립. 리뷰 라벨의 긍정·부정 비율로 계산
    mentions: int  # 이 장소 리뷰에서 해당 aspect가 언급된 라벨 수
    evidence: str | None  # 대표 근거 문구 (리뷰 원문 그대로)


class RecommendationItem(BaseModel):
    rank: int
    place_id: int
    place_name: str | None
    category: str
    scrap_ids: list[int]
    fit: float  # 0~100, 요구사항 가중치로 평균 낸 만족도
    review_count: int
    reason: str
    strengths: list[AspectScore]
    cautions: list[AspectScore]


class SkippedScrap(BaseModel):
    scrap_id: int
    reason: str


class RecommendationResponse(BaseModel):
    requirements: str
    weights: list[AspectWeight]  # 비어 있으면 요구사항에서 키워드를 찾지 못해 전체 만족도로 순위를 매긴 것
    items: list[RecommendationItem]
    skipped: list[SkippedScrap]
