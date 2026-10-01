from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class ReviewAnnotation(Base):
    __tablename__ = "review_annotations"
    __table_args__ = (
        CheckConstraint("sentiment IN ('positive', 'negative', 'neutral')"),
        CheckConstraint("annotation_tier IN ('gold', 'silver', 'model')"),
        CheckConstraint("evidence_start >= 0 AND evidence_end > evidence_start"),
        UniqueConstraint("review_id", "aspect_id", "attribute_value", "sentiment", "evidence_text"),
        Index("idx_annotations_review", "review_id"),
        Index("idx_annotations_aspect", "aspect_id"),
    )

    annotation_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    review_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("reviews.review_id", ondelete="CASCADE"))
    aspect_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("aspects.aspect_id", ondelete="RESTRICT"))
    attribute_value: Mapped[str] = mapped_column(String(100))
    sentiment: Mapped[str] = mapped_column(String(10))
    evidence_text: Mapped[str] = mapped_column(Text)
    evidence_start: Mapped[int] = mapped_column(Integer)
    evidence_end: Mapped[int] = mapped_column(Integer)
    annotation_tier: Mapped[str] = mapped_column(String(20))
    created_by: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
