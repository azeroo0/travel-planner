from typing import Literal

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
    # 요구사항과 관련된 리뷰가 있는지. False면 fit은 리뷰 전반 만족도이고, 관련 장소들 뒤에 놓인다.
    matched: bool
    review_count: int
    reason: str
    strengths: list[AspectScore]
    cautions: list[AspectScore]


class SkippedScrap(BaseModel):
    scrap_id: int
    reason: str


class RecommendationResponse(BaseModel):
    requirements: str
    # 요구사항을 해석한 방식. model: 파인튜닝 모델 + 동행 키워드, keywords: 모델을 쓸 수 없어 키워드 규칙만 사용
    interpreter: Literal["model", "keywords"]
    weights: list[AspectWeight]  # 비어 있으면 요구사항에서 키워드를 찾지 못해 전체 만족도로 순위를 매긴 것
    # "주차는 필요 없어요"처럼 신경 쓰지 않는다고 한 항목 (가중치에서 제외). model이면 aspect 이름, keywords면 키워드
    ignored_keywords: list[str]
    items: list[RecommendationItem]
    skipped: list[SkippedScrap]


Category = Literal["hotel", "restaurant", "attraction"]
Region = Literal["haeundae", "gwangan", "seomyeon", "wondo", "west"]
Companion = Literal["solo", "friends", "couple", "parents", "kids"]
Walk = Literal["ok", "moderate", "low"]


class PlaceRecommendationQuery(BaseModel):
    companion: Companion | None = None
    walk: Walk | None = None
    priorities: list[Literal["sea", "food", "photo", "culture", "rest", "quiet"]] = Field(default_factory=list)
    avoids: list[Literal["waiting", "stairs", "noise", "parking", "crowd"]] = Field(default_factory=list)
    category: Category | None = None
    limit: int = Field(default=10, ge=1, le=50)


class RecommendedPlace(BaseModel):
    place_id: int
    name: str
    category: Category
    region: Region


class FitFactor(BaseModel):
    aspect: str
    polarity: Literal["positive", "negative", "neutral"]
    share: float
    weight: float
    delta: float


class FitResult(BaseModel):
    place: RecommendedPlace
    fit: float = Field(ge=0, le=100)
    reason: str
    strengths: list[FitFactor] = Field(default_factory=list)
    cautions: list[FitFactor] = Field(default_factory=list)
