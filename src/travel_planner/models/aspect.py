from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from travel_planner.db.base import Base


class Aspect(Base):
    __tablename__ = "aspects"
    __table_args__ = (UniqueConstraint("category_id", "aspect_name"),)

    aspect_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    category_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("place_categories.category_id", ondelete="CASCADE"))
    aspect_name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"))


class AspectValue(Base):
    __tablename__ = "aspect_values"
    __table_args__ = (UniqueConstraint("aspect_id", "value_name"),)

    value_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    aspect_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("aspects.aspect_id", ondelete="CASCADE"))
    value_name: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("TRUE"))
