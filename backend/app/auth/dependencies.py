"""Reusable FastAPI authentication and role-authorization dependencies."""

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.identity import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _credentials_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Annotated[Session, Depends(get_db)],
) -> User:
    """Validate a bearer token and return its current active database user."""
    try:
        payload = decode_access_token(token)
        user_id = UUID(str(payload["sub"]))
    except (InvalidTokenError, KeyError, TypeError, ValueError, RuntimeError) as error:
        raise _credentials_error() from error

    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise _credentials_error()
    return user


def require_roles(*allowed_roles: UserRole) -> Callable[..., User]:
    """Create a dependency that admits only users with one of the given roles."""

    def role_dependency(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return role_dependency
