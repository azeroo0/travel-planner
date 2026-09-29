from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class CompanionType(Base):
    __tablename__ = "companion_types"

    companion_type_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    companion_code: Mapped[str] = mapped_column(String(50), unique=True)
    companion_name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"))


class ReviewCompanion(Base):
    __tablename__ = "review_companions"
    __table_args__ = (Index("idx_review_companions_review", "review_id"),)

    review_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("reviews.review_id", ondelete="CASCADE"), primary_key=True)
    companion_type_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("companion_types.companion_type_id", ondelete="CASCADE"), primary_key=True)
