from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PlaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    place_id: int
    category_id: int
    district_id: int | None
    source: str
    source_place_id: str
    place_name: str | None
    address: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    intro_text: str | None
    created_at: datetime
    updated_at: datetime


class PlaceImageRead(BaseModel):
    image_url: str
    is_main: bool
    sort_order: int


class PlaceTagRead(BaseModel):
    category: str | None
    tag_name: str


class PlaceDetailRead(PlaceRead):
    name: str | None
    category: str
    region: str | None
    district: str | None
    latitude: float | None
    longitude: float | None
    summary: str
    main_image_url: str | None
    review_count: int
    images: list[PlaceImageRead]
    tags: list[PlaceTagRead]


class ProfileAspect(BaseModel):
    aspect: str
    polarity: str
    share: float  # 해당 aspect를 이 polarity로 언급한 리뷰 비율(%)
    mentions: int  # 해당 aspect를 이 polarity로 언급한 리뷰 수


class ProfileContext(BaseModel):
    context: str
    ratio: float  # 이 동행 유형이 표시된 리뷰 비율(%)


class PlaceProfile(BaseModel):
    place_id: int
    review_count: int
    aspects: list[ProfileAspect]
    contexts: list[ProfileContext]
    # 동행 유형별 긍정 annotation 비율(%) = positive / (positive + negative)
    context_satisfaction: dict[str, float]


class EvidenceReview(BaseModel):
    review_id: int
    text: str
    context: str
    attribute: str
    sentiment: str
    evidence_start: int
    evidence_end: int
