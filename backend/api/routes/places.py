from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_session
from backend.repositories import places as place_repository
from backend.schemas.places import PlaceRead

router = APIRouter(prefix="/places", tags=["places"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=list[PlaceRead])
async def list_places(
    session: Session,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[PlaceRead]:
    places = await place_repository.list_places(session, limit=limit, offset=offset)
    return [PlaceRead.model_validate(place) for place in places]


@router.get("/{place_id}", response_model=PlaceRead)
async def get_place(place_id: int, session: Session) -> PlaceRead:
    place = await place_repository.get_place(session, place_id)
    if place is None:
        raise HTTPException(status_code=404, detail="Place not found")
    return PlaceRead.model_validate(place)
