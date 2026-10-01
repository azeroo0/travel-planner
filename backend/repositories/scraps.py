from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.scrap import Scrap, ScrapContent
from backend.schemas.scraps import ScrapCreate


async def create_scrap(session: AsyncSession, *, user_id: int, request: ScrapCreate) -> Scrap:
    scrap = Scrap(user_id=user_id, **request.model_dump())
    session.add(scrap)
    await session.flush()
    await session.refresh(scrap)
    return scrap


async def list_scraps(
    session: AsyncSession, *, user_id: int, limit: int, offset: int, source_type: str | None = None,
) -> list[Scrap]:
    query = select(Scrap).where(Scrap.user_id == user_id)
    if source_type is not None:
        query = query.where(Scrap.source_type == source_type)
    result = await session.scalars(
        query.order_by(Scrap.created_at.desc(), Scrap.scrap_id.desc()).limit(limit).offset(offset)
    )
    return list(result)


async def get_scrap(session: AsyncSession, *, scrap_id: int, user_id: int) -> Scrap | None:
    return await session.scalar(
        select(Scrap).where(Scrap.scrap_id == scrap_id, Scrap.user_id == user_id)
    )


async def get_content(session: AsyncSession, scrap_id: int) -> ScrapContent | None:
    return await session.get(ScrapContent, scrap_id)


async def update_title(session: AsyncSession, scrap: Scrap, title: str | None) -> Scrap:
    scrap.title = title
    scrap.updated_at = func.current_timestamp()
    await session.flush()
    await session.refresh(scrap)
    return scrap


async def delete_scrap(session: AsyncSession, scrap: Scrap) -> None:
    await session.delete(scrap)
