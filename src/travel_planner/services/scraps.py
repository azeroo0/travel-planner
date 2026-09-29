from sqlalchemy.ext.asyncio import AsyncSession

from travel_planner.repositories import scraps as scrap_repository
from travel_planner.schemas.scraps import ScrapCreate, ScrapRead


async def create_scrap(session: AsyncSession, *, user_id: int, request: ScrapCreate) -> ScrapRead:
    scrap = await scrap_repository.create_scrap(session, user_id=user_id, request=request)
    await session.commit()
    return ScrapRead.model_validate(scrap)


async def get_scrap(session: AsyncSession, *, scrap_id: int, user_id: int) -> ScrapRead | None:
    scrap = await scrap_repository.get_scrap(session, scrap_id=scrap_id, user_id=user_id)
    return ScrapRead.model_validate(scrap) if scrap is not None else None


async def delete_scrap(session: AsyncSession, *, scrap_id: int, user_id: int) -> bool:
    scrap = await scrap_repository.get_scrap(session, scrap_id=scrap_id, user_id=user_id)
    if scrap is None:
        return False
    await scrap_repository.delete_scrap(session, scrap)
    await session.commit()
    return True
