from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from backend.core.config import get_settings

_password_hash = PasswordHash.recommended()  # argon2


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    return password_hash is not None and _password_hash.verify(password, password_hash)


def _secret() -> str:
    secret = get_settings().jwt_secret
    if not secret:
        raise RuntimeError("JWT_SECRET is required for authentication")
    return secret


def create_access_token(user_id: int) -> tuple[str, int]:
    """(토큰, 만료까지 남은 초)를 반환한다."""
    settings = get_settings()
    expires_in = settings.access_token_expire_minutes * 60
    payload = {"sub": str(user_id), "exp": datetime.now(UTC) + timedelta(seconds=expires_in)}
    return jwt.encode(payload, _secret(), algorithm=settings.jwt_algorithm), expires_in


def decode_access_token(token: str) -> int | None:
    """유효한 토큰이면 user_id, 만료·위조·형식 오류면 None."""
    try:
        payload = jwt.decode(token, _secret(), algorithms=[get_settings().jwt_algorithm])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
