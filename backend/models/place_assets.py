from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class PlaceImage(Base):
    __tablename__ = "place_images"

    image_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    place_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("places.place_id"))
    image_url: Mapped[str] = mapped_column(String(1000))
    is_main: Mapped[bool] = mapped_column(Boolean)
    sort_order: Mapped[int] = mapped_column(Integer)


class Tag(Base):
    __tablename__ = "tags"

    tag_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    category: Mapped[str | None] = mapped_column(String(50))
    tag_name: Mapped[str] = mapped_column(String(100))


class PlaceTag(Base):
    __tablename__ = "place_tags"

    place_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("places.place_id"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tags.tag_id"), primary_key=True)
