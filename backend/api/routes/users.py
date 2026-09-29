from fastapi import APIRouter

from backend.api.deps import CurrentUser, Session
from backend.schemas.users import UserRead, UserUpdate
from backend.services import users as user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def read_me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


@router.patch("/me", response_model=UserRead)
async def update_me(request: UserUpdate, user: CurrentUser, session: Session) -> UserRead:
    return await user_service.update_me(session, user, request)
