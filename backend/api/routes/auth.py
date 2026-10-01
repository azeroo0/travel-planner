from fastapi import APIRouter, HTTPException

from backend.api.deps import Session
from backend.schemas.users import LoginRequest, SignupRequest, TokenResponse, UserRead
from backend.services import users as user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=201, response_model=UserRead)
async def signup(request: SignupRequest, session: Session) -> UserRead:
    try:
        return await user_service.signup(session, request)
    except user_service.EmailAlreadyExists:
        raise HTTPException(status_code=409, detail="Email already registered") from None


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, session: Session) -> TokenResponse:
    token = await user_service.login(session, request)
    if token is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return token
