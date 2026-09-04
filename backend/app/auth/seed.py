"""Explicit, idempotent demo-user seeding for local MVP use."""

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.auth.service import normalize_email
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.enums import UserRole
from app.models.identity import User

DEMO_USERS: tuple[tuple[str, str, UserRole], ...] = (
    ("Demo Admin", "demo.admin@honeychain.local", UserRole.ADMIN),
    ("Demo Beekeeper", "demo.beekeeper@honeychain.local", UserRole.BEEKEEPER),
    ("Demo Processor", "demo.processor@honeychain.local", UserRole.PROCESSOR),
)


def seed_demo_users(session: Session, password: str) -> Sequence[User]:
    """Create missing demo users without altering any existing account."""
    created: list[User] = []
    for name, email, role in DEMO_USERS:
        normalized_email = normalize_email(email)
        existing = session.scalar(select(User).where(func.lower(User.email) == normalized_email))
        if existing is None:
            user = User(
                name=name,
                email=normalized_email,
                password_hash=hash_password(password),
                role=role,
                is_active=True,
            )
            session.add(user)
            created.append(user)
    session.commit()
    return created


def main() -> None:
    """Run the explicit local demo seed command without revealing credentials."""
    if SessionLocal is None:
        raise RuntimeError("HONEY_CHAIN_DATABASE_URL must be configured before seeding users.")

    with SessionLocal() as session:
        created = seed_demo_users(session, settings.demo_password_value())
    print(f"Demo user seed complete: {len(created)} user(s) created.")


if __name__ == "__main__":
    main()
