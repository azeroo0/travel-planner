from sqlalchemy import BigInteger, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class Region(Base):
    __tablename__ = "regions"

    region_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    region_code: Mapped[str] = mapped_column(String(20), unique=True)
    region_name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)


class District(Base):
    __tablename__ = "districts"
    __table_args__ = (UniqueConstraint("region_id", "district_name"),)

    district_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    region_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("regions.region_id", ondelete="RESTRICT"))
    district_name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)


class PlaceCategory(Base):
    __tablename__ = "place_categories"

    category_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    category_code: Mapped[str] = mapped_column(String(30), unique=True)
    category_name: Mapped[str] = mapped_column(String(50), unique=True)
