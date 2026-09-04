"""Alembic environment wired to application settings and metadata."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection

from app.core.config import settings
from app.core.database import engine
from app.db.base import Base
import app.models  # noqa: F401  # Future model modules are imported there.


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    """Return the database URL supplied through application settings."""
    if settings.database_url:
        return settings.database_url
    raise RuntimeError("HONEY_CHAIN_DATABASE_URL must be configured for Alembic.")


def run_migrations_offline() -> None:
    """Run migrations without creating a database connection."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using the application's centralized SQLAlchemy engine."""
    if engine is None:
        raise RuntimeError("HONEY_CHAIN_DATABASE_URL must be configured for Alembic.")

    with engine.connect() as connection:
        _run_migrations(connection)


def _run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
