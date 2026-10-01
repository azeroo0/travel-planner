from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class Scrap(Base):
    __tablename__ = "scraps"
    __table_args__ = (CheckConstraint("place_id IS NOT NULL OR review_id IS NOT NULL OR source_url IS NOT NULL", name="ck_scraps_target"),)

    scrap_id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"))
    place_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("places.place_id", ondelete="SET NULL"))
    review_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("reviews.review_id", ondelete="SET NULL"))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    title: Mapped[str | None] = mapped_column(String(300))
    source_type: Mapped[str] = mapped_column(String(30), server_default=text("'internal'"))
    status: Mapped[str] = mapped_column(String(20), server_default=text("'ready'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=text("CURRENT_TIMESTAMP"))


class ScrapContent(Base):
    __tablename__ = "scrap_contents"

    scrap_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("scraps.scrap_id", ondelete="CASCADE"), primary_key=True)
    content_text: Mapped[str | None] = mapped_column(Text)
    extraction_method: Mapped[str | None] = mapped_column(String(30))
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), server_default=text("CURRENT_TIMESTAMP"))
