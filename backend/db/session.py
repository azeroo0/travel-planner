from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.core.config import get_settings


def async_database_url(database_url: str) -> tuple[str, dict]:
    """postgresql://·postgres://·postgresql+psycopg:// 주소도 asyncpg 주소로 바꾼다.

    Supabase 등이 주는 주소를 그대로 쓸 수 있게 한다. asyncpg는 sslmode 파라미터를 모르므로
    connect_args의 ssl로 옮긴다. (주소, create_async_engine에 넘길 connect_args)를 반환한다.
    """
    url = make_url(database_url)
    if url.get_backend_name() not in {"postgresql", "postgres"}:
        raise RuntimeError("DATABASE_URL must be a PostgreSQL URL")
    url = url.set(drivername="postgresql+asyncpg")
    connect_args: dict = {}
    sslmode = url.query.get("sslmode")
    if sslmode:
        url = url.difference_update_query(["sslmode"])
        if sslmode != "disable":
            connect_args["ssl"] = "require" if sslmode in {"require", "prefer", "allow"} else sslmode
    return url.render_as_string(hide_password=False), connect_args


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    database_url = get_settings().database_url
    if not database_url:
        raise RuntimeError("DATABASE_URL is required for database operations")
    url, connect_args = async_database_url(database_url)
    engine = create_async_engine(url, pool_pre_ping=True, connect_args=connect_args)
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session
