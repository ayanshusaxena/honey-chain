from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

import app.models  # noqa: F401
from app.db.base import Base


def test_alembic_configuration_and_metadata() -> None:
    """Confirm Alembic loads and points at the sole project metadata object."""
    config = Config(Path(__file__).parents[1] / "alembic.ini")
    scripts = ScriptDirectory.from_config(config)

    assert len(scripts.get_heads()) == 1
    assert len(Base.metadata.tables) == 15
