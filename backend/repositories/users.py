from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.user import User


def _normalize_email(email: str) -> str:
    return email.strip().lower()


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(func.lower(User.email) == _normalize_email(email)))


async def create_user(session: AsyncSession, *, email: str, password_hash: str, name: str | None) -> User:
    user = User(email=_normalize_email(email), password_hash=password_hash, name=name)
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user
