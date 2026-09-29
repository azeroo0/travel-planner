from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from travel_planner.db.base import Base


class Place(Base):
    __tablename__ = "places"
    __table_args__ = (UniqueConstraint("source", "source_place_id"),)

    place_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    category_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("place_categories.category_id", ondelete="RESTRICT"))
    district_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("districts.district_id", ondelete="RESTRICT"))
    source: Mapped[str] = mapped_column(String(50))
    source_place_id: Mapped[str] = mapped_column(String(200))
    place_name: Mapped[str | None] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(String(500))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    intro_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
