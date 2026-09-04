import pytest
from sqlalchemy import text

from app.core.database import SessionLocal


@pytest.mark.skipif(
    SessionLocal is None,
    reason="HONEY_CHAIN_DATABASE_URL is not configured.",
)
def test_database_connection() -> None:
    """Confirm the configured database session can execute a trivial query."""
    assert SessionLocal is not None

    with SessionLocal() as session:
        assert session.scalar(text("SELECT 1")) == 1
