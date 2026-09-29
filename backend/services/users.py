from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import create_access_token, hash_password, verify_password
from backend.models.user import User
from backend.repositories import users as user_repository
from backend.schemas.users import LoginRequest, SignupRequest, TokenResponse, UserRead, UserUpdate


class EmailAlreadyExists(Exception):
    pass


async def signup(session: AsyncSession, request: SignupRequest) -> UserRead:
    if await user_repository.get_by_email(session, request.email) is not None:
        raise EmailAlreadyExists
    try:
        user = await user_repository.create_user(
            session, email=request.email, password_hash=hash_password(request.password), name=request.name,
        )
        await session.commit()
    except IntegrityError as error:  # 동시에 같은 이메일로 가입한 경우
        await session.rollback()
        raise EmailAlreadyExists from error
    return UserRead.model_validate(user)


async def login(session: AsyncSession, request: LoginRequest) -> TokenResponse | None:
    """이메일이 없거나 비밀번호가 틀리면 구분 없이 None."""
    user = await user_repository.get_by_email(session, request.email)
    if user is None or not verify_password(request.password, user.password_hash):
        return None
    token, expires_in = create_access_token(user.user_id)
    return TokenResponse(access_token=token, expires_in=expires_in, user=UserRead.model_validate(user))


async def update_me(session: AsyncSession, user: User, request: UserUpdate) -> UserRead:
    fields = request.model_dump(exclude_unset=True)
    if "name" in fields:
        user.name = fields["name"]
    if fields.get("password") is not None:
        user.password_hash = hash_password(fields["password"])
    if fields:
        user.updated_at = func.now()
        await session.commit()
        await session.refresh(user)
    return UserRead.model_validate(user)
