import pytest
from sqlalchemy import inspect

import app.models  # noqa: F401
from app.core.database import engine
from app.db.base import Base
from app.models.enums import BatchStatus, QrStatus, UserRole


APPLICATION_TABLES = {
    "audit_events",
    "batch_collection_lots",
    "batches",
    "blockchain_records",
    "collection_lot_harvests",
    "collection_lots",
    "harvests",
    "hive_harvests",
    "hives",
    "lab_evidence",
    "packaging_lots",
    "qr_tokens",
    "risk_events",
    "telemetry",
    "users",
}


def test_all_approved_models_are_registered() -> None:
    assert set(Base.metadata.tables) == APPLICATION_TABLES


def test_important_enum_values_are_locked() -> None:
    assert [role.value for role in UserRole] == ["ADMIN", "BEEKEEPER", "PROCESSOR"]
    assert [status.value for status in BatchStatus] == ["ACTIVE", "HOLD", "RECALL"]
    assert [status.value for status in QrStatus] == ["ACTIVE", "REVOKED"]


@pytest.mark.skipif(engine is None, reason="HONEY_CHAIN_DATABASE_URL is not configured.")
def test_migrated_schema_contains_all_application_tables() -> None:
    assert engine is not None

    tables = set(inspect(engine).get_table_names(schema="public"))

    assert APPLICATION_TABLES.issubset(tables)
