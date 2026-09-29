from fastapi import APIRouter, HTTPException

from travel_planner.schemas.scraps import ScrapCreate

router = APIRouter(prefix="/scraps", tags=["scraps"])


def authentication_not_configured() -> None:
    raise HTTPException(status_code=501, detail="Scrap API requires an authenticated user")


@router.post("")
async def create_scrap(request: ScrapCreate) -> None:
    authentication_not_configured()


@router.get("/{scrap_id}")
async def get_scrap(scrap_id: int) -> None:
    authentication_not_configured()


@router.delete("/{scrap_id}")
async def delete_scrap(scrap_id: int) -> None:
    authentication_not_configured()
