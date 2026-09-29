from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.scrap import Scrap
from backend.schemas.scraps import ScrapCreate


async def create_scrap(session: AsyncSession, *, user_id: int, request: ScrapCreate) -> Scrap:
    scrap = Scrap(user_id=user_id, **request.model_dump())
    session.add(scrap)
    await session.flush()
    await session.refresh(scrap)
    return scrap


async def get_scrap(session: AsyncSession, *, scrap_id: int, user_id: int) -> Scrap | None:
    return await session.scalar(
        select(Scrap).where(Scrap.scrap_id == scrap_id, Scrap.user_id == user_id)
    )


async def delete_scrap(session: AsyncSession, scrap: Scrap) -> None:
    await session.delete(scrap)
