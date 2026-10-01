from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScrapCreate(BaseModel):
    place_id: int | None = Field(default=None, gt=0)
    review_id: int | None = Field(default=None, gt=0)
    source_url: str | None = Field(default=None, max_length=1000)
    title: str | None = Field(default=None, max_length=300)
    source_type: str = Field(default="internal", max_length=30)

    @model_validator(mode="after")
    def require_target(self) -> "ScrapCreate":
        if self.place_id is None and self.review_id is None and self.source_url is None:
            raise ValueError("place_id, review_id, or source_url is required")
        return self


class ScrapRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scrap_id: int
    user_id: int
    place_id: int | None
    review_id: int | None
    source_url: str | None
    title: str | None
    source_type: str
    status: str
    created_at: datetime
    updated_at: datetime


class ScrapUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=300)


class ScrapContentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    content_text: str | None
    extraction_method: str | None
    fetched_at: datetime | None


class ScrapDetail(ScrapRead):
    content: ScrapContentRead | None = None
