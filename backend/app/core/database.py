"""Centralized SQLAlchemy database engine and session management."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def _create_engine(database_url: str) -> Engine:
    """Create the application's synchronous PostgreSQL engine."""
    return create_engine(database_url, pool_pre_ping=True)


engine = _create_engine(settings.database_url) if settings.database_url else None
SessionLocal = (
    sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    if engine
    else None
)


def get_db() -> Generator[Session, None, None]:
    """Yield one database session for a FastAPI request."""
    if SessionLocal is None:
        message = "HONEY_CHAIN_DATABASE_URL must be configured before using the database."
        raise RuntimeError(message)

    with SessionLocal() as session:
        yield session
