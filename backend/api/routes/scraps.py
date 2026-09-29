from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response

from backend.api.deps import CurrentUser, Session
from backend.schemas.scraps import ScrapCreate, ScrapDetail, ScrapRead, ScrapUpdate
from backend.services import scraps as scrap_service

router = APIRouter(prefix="/scraps", tags=["scraps"])


def _not_found() -> HTTPException:
    # 다른 사용자의 스크랩도 존재 여부를 드러내지 않도록 404로 응답한다.
    return HTTPException(status_code=404, detail="Scrap not found")


@router.post("", status_code=201, response_model=ScrapRead)
async def create_scrap(request: ScrapCreate, user: CurrentUser, session: Session) -> ScrapRead:
    return await scrap_service.create_scrap(session, user_id=user.user_id, request=request)


@router.get("", response_model=list[ScrapRead])
async def list_scraps(
    user: CurrentUser,
    session: Session,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    source_type: Annotated[str | None, Query(max_length=30)] = None,
) -> list[ScrapRead]:
    return await scrap_service.list_scraps(
        session, user_id=user.user_id, limit=limit, offset=offset, source_type=source_type,
    )


@router.get("/{scrap_id}", response_model=ScrapDetail)
async def get_scrap(scrap_id: int, user: CurrentUser, session: Session) -> ScrapDetail:
    scrap = await scrap_service.get_scrap(session, scrap_id=scrap_id, user_id=user.user_id)
    if scrap is None:
        raise _not_found()
    return scrap


@router.patch("/{scrap_id}", response_model=ScrapRead)
async def update_scrap(scrap_id: int, request: ScrapUpdate, user: CurrentUser, session: Session) -> ScrapRead:
    scrap = await scrap_service.update_scrap(session, scrap_id=scrap_id, user_id=user.user_id, request=request)
    if scrap is None:
        raise _not_found()
    return scrap


@router.delete("/{scrap_id}", status_code=204)
async def delete_scrap(scrap_id: int, user: CurrentUser, session: Session) -> Response:
    if not await scrap_service.delete_scrap(session, scrap_id=scrap_id, user_id=user.user_id):
        raise _not_found()
    return Response(status_code=204)
