"""Authentication operations backed by the users table."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.security import verify_password
from app.models.identity import User


def normalize_email(email: str) -> str:
    """Normalize email addresses before lookup or storage."""
    return email.strip().lower()


def authenticate_user(session: Session, email: str, password: str) -> User | None:
    """Return an active user only when the supplied credentials are valid."""
    normalized_email = normalize_email(email)
    user = session.scalar(select(User).where(func.lower(User.email) == normalized_email))

    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
