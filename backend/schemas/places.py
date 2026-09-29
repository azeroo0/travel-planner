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
