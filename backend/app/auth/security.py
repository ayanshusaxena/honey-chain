"""Password hashing and signed access-token helpers."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import settings
from app.models.enums import UserRole

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Create an Argon2id password hash."""
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Return whether a password matches its stored hash."""
    try:
        return password_hash.verify(password, hashed_password)
    except (ValueError, TypeError):
        return False


def create_access_token(
    subject: UUID,
    role: UserRole,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed, expiring JWT access token."""
    expires_at = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {"sub": str(subject), "role": role.value, "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret_value(), algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, object]:
    """Validate a JWT signature and expiry, returning its claims."""
    return jwt.decode(
        token,
        settings.jwt_secret_value(),
        algorithms=[settings.jwt_algorithm],
        options={"require": ["sub", "role", "exp"]},
    )


__all__ = [
    "InvalidTokenError",
    "create_access_token",
    "decode_access_token",
    "hash_password",
    "verify_password",
]
