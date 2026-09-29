from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.place import Place


async def list_places(session: AsyncSession, *, limit: int, offset: int) -> list[Place]:
    result = await session.scalars(select(Place).order_by(Place.place_id).limit(limit).offset(offset))
    return list(result)


async def get_place(session: AsyncSession, place_id: int) -> Place | None:
    return await session.get(Place, place_id)
