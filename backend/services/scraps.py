from sqlalchemy.ext.asyncio import AsyncSession

from backend.repositories import scraps as scrap_repository
from backend.schemas.scraps import ScrapContentRead, ScrapCreate, ScrapDetail, ScrapRead, ScrapUpdate


async def create_scrap(session: AsyncSession, *, user_id: int, request: ScrapCreate) -> ScrapRead:
    scrap = await scrap_repository.create_scrap(session, user_id=user_id, request=request)
    await session.commit()
    return ScrapRead.model_validate(scrap)


async def list_scraps(
    session: AsyncSession, *, user_id: int, limit: int, offset: int, source_type: str | None = None,
) -> list[ScrapRead]:
    scraps = await scrap_repository.list_scraps(
        session, user_id=user_id, limit=limit, offset=offset, source_type=source_type,
    )
    return [ScrapRead.model_validate(scrap) for scrap in scraps]


async def get_scrap(session: AsyncSession, *, scrap_id: int, user_id: int) -> ScrapDetail | None:
    scrap = await scrap_repository.get_scrap(session, scrap_id=scrap_id, user_id=user_id)
    if scrap is None:
        return None
    content = await scrap_repository.get_content(session, scrap_id)
    return ScrapDetail(
        **ScrapRead.model_validate(scrap).model_dump(),
        content=ScrapContentRead.model_validate(content) if content is not None else None,
    )


async def update_scrap(
    session: AsyncSession, *, scrap_id: int, user_id: int, request: ScrapUpdate,
) -> ScrapRead | None:
    scrap = await scrap_repository.get_scrap(session, scrap_id=scrap_id, user_id=user_id)
    if scrap is None:
        return None
    if "title" in request.model_fields_set:
        scrap = await scrap_repository.update_title(session, scrap, request.title)
        await session.commit()
    return ScrapRead.model_validate(scrap)


async def delete_scrap(session: AsyncSession, *, scrap_id: int, user_id: int) -> bool:
    scrap = await scrap_repository.get_scrap(session, scrap_id=scrap_id, user_id=user_id)
    if scrap is None:
        return False
    await scrap_repository.delete_scrap(session, scrap)
    await session.commit()
    return True
