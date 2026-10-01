from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("source", "external_review_id"),
        CheckConstraint("dataset_split IN ('train', 'val', 'test')"),
        CheckConstraint("label_tier IN ('gold', 'silver')"),
    )

    review_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    place_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("places.place_id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(50))
    external_review_id: Mapped[str] = mapped_column(String(200))
    source_member: Mapped[str | None] = mapped_column(String(50))
    # 학습 데이터셋 리뷰만 값이 있고, 서비스용 실제 리뷰(Tripadvisor 등)는 NULL이다.
    dataset_split: Mapped[str | None] = mapped_column(String(20))
    label_tier: Mapped[str | None] = mapped_column(String(20))
    is_synthetic: Mapped[bool] = mapped_column(Boolean)
    review_text: Mapped[str] = mapped_column(Text)
    raw_record: Mapped[dict[str, Any]] = mapped_column(JSONB)
    crawled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
