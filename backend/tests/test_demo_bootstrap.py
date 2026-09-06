"""Tests for Phase 3 Demo Reproducibility and Synthetic Dataset Bootstrap."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.demo.bootstrap import (
    DEMO_ADMIN_EMAIL,
    DEMO_BATCH_PREFIX,
    DEMO_CERT_PREFIX,
    DEMO_HARVEST_CODE,
    DEMO_HIVE_CODE,
    DEMO_LOT_CODE,
    DEMO_PKG_PREFIX,
    DEMO_PREFIX,
    SYNTHETIC_DISCLAIMER,
    bootstrap_demo_dataset,
    is_node_online,
    reset_demo_data,
)
from app.models.enums import BatchStatus, LabEvidenceStatus, QrStatus, TelemetryQuality, UserRole
from app.models.evidence import BlockchainRecord, LabEvidence, PackagingLot, QrToken
from app.models.hive import Harvest, Hive, HiveHarvest, RiskEvent, Telemetry
from app.models.identity import User
from app.models.traceability import Batch
from app.qr.service import verify_consumer_token


@pytest.fixture
def db_session() -> Session:
    if SessionLocal is None:
        pytest.skip("HONEY_CHAIN_DATABASE_URL is not configured.")

    with SessionLocal() as session:
        reset_demo_data(session)
        try:
            yield session
        finally:
            reset_demo_data(session)


def test_demo_bootstrap_creates_expected_lineage_and_prerequisites(db_session: Session) -> None:
    """Verify that demo bootstrap creates complete, valid, coherent lineage satisfying all prerequisites."""
    result = bootstrap_demo_dataset(db_session, include_blockchain=False)

    # 1. Check returned metadata
    assert result.hive_code == DEMO_HIVE_CODE
    assert "DEMO / SIMULATED" in result.hive_region
    assert result.harvest_code == DEMO_HARVEST_CODE
    assert result.harvest_quantity_kg == 60.0
    assert result.lot_code == DEMO_LOT_CODE
    assert result.lot_quantity_kg == 60.0
    assert result.batch_code.startswith(DEMO_BATCH_PREFIX)
    assert result.batch_derived_quantity_kg == 60.0
    assert result.certificate_id.startswith(DEMO_CERT_PREFIX)
    assert len(result.file_hash_sha256) == 64
    assert result.package_lot_code.startswith(DEMO_PKG_PREFIX)
    assert result.packaged_quantity_kg == 50.0
    assert result.consumer_verification_status == "VERIFIED"
    assert result.synthetic_disclaimer == SYNTHETIC_DISCLAIMER

    # 2. Check Database State: Batch Prerequisites
    batch = db_session.get(Batch, result.batch_id)
    assert batch is not None
    assert batch.is_finalized is True
    assert batch.status == BatchStatus.ACTIVE

    # 3. Check Database State: Lab Evidence
    evidence = db_session.get(LabEvidence, result.lab_evidence_id)
    assert evidence is not None
    assert evidence.status == LabEvidenceStatus.ACTIVE
    assert evidence.file_hash_sha256 == result.file_hash_sha256
    assert "DEMO / SIMULATED" in evidence.test_summary

    # 4. Check Database State: Packaging Lot
    pkg_lot = db_session.get(PackagingLot, result.packaging_lot_id)
    assert pkg_lot is not None
    assert pkg_lot.batch_id == batch.id
    assert (pkg_lot.quantity * float(pkg_lot.package_size_grams) / 1000.0) == 50.0
    assert 50.0 <= result.batch_derived_quantity_kg


def test_demo_bootstrap_safe_repeatability(db_session: Session) -> None:
    """Verify that multiple consecutive bootstrap executions safely reconcile and do not duplicate state."""
    # Run 1
    res1 = bootstrap_demo_dataset(db_session, include_blockchain=False)
    assert res1.hive_code == DEMO_HIVE_CODE

    count_batches_1 = db_session.scalar(
        select(func.count()).select_from(Batch).where(Batch.batch_code.like(f"{DEMO_PREFIX}%"))
    )
    assert count_batches_1 == 1

    # Run 2
    res2 = bootstrap_demo_dataset(db_session, include_blockchain=False)
    assert res2.hive_code == DEMO_HIVE_CODE

    count_batches_2 = db_session.scalar(
        select(func.count()).select_from(Batch).where(Batch.batch_code.like(f"{DEMO_PREFIX}%"))
    )
    assert count_batches_2 == 1

    count_hives_2 = db_session.scalar(
        select(func.count()).select_from(Hive).where(Hive.hive_code.like(f"{DEMO_PREFIX}%"))
    )
    assert count_hives_2 == 1

    count_pkgs_2 = db_session.scalar(
        select(func.count()).select_from(PackagingLot).where(PackagingLot.package_lot_code.like(f"{DEMO_PREFIX}%"))
    )
    assert count_pkgs_2 == 1

    # Run 3
    res3 = bootstrap_demo_dataset(db_session, include_blockchain=False)
    assert res3.hive_code == DEMO_HIVE_CODE

    count_batches_3 = db_session.scalar(
        select(func.count()).select_from(Batch).where(Batch.batch_code.like(f"{DEMO_PREFIX}%"))
    )
    assert count_batches_3 == 1


def test_demo_reset_and_bootstrap_preserves_unrelated_sentinel_data(db_session: Session) -> None:
    """Verify that demo bootstrap and reset NEVER touch unrelated operational / sentinel records."""
    # 1. Create unrelated sentinel entities
    sentinel_user = User(
        id=uuid4(),
        name="Sentinel Operational User",
        email=f"sentinel-{uuid4().hex[:6]}@operational.test",
        password_hash="fakehash",
        role=UserRole.BEEKEEPER,
        is_active=True,
    )
    db_session.add(sentinel_user)
    db_session.commit()
    db_session.refresh(sentinel_user)

    sentinel_hive = Hive(
        id=uuid4(),
        hive_code=f"SENTINEL-HIV-{uuid4().hex[:6].upper()}",
        location_region="Real Commercial Apiary - Himachal",
        beekeeper_id=sentinel_user.id,
        is_active=True,
    )
    db_session.add(sentinel_hive)
    db_session.commit()
    db_session.refresh(sentinel_hive)

    sentinel_telem = Telemetry(
        id=uuid4(),
        hive_id=sentinel_hive.id,
        device_timestamp=datetime.now(UTC),
        received_at=datetime.now(UTC),
        weight_kg=42.0,
        temperature_c=35.0,
        humidity_pct=60.0,
        quality=TelemetryQuality.VALID,
    )
    db_session.add(sentinel_telem)
    db_session.commit()
    db_session.refresh(sentinel_telem)

    try:
        # 2. Run bootstrap
        bootstrap_demo_dataset(db_session, include_blockchain=False)

        # 3. Assert sentinels survive bootstrap
        assert db_session.get(User, sentinel_user.id) is not None
        assert db_session.get(Hive, sentinel_hive.id) is not None
        assert db_session.get(Telemetry, sentinel_telem.id) is not None

        # 4. Run explicit reset
        deleted = reset_demo_data(db_session)
        assert deleted.get("hives", 0) >= 1

        # 5. Assert sentinels survive reset
        assert db_session.get(User, sentinel_user.id) is not None
        assert db_session.get(Hive, sentinel_hive.id) is not None
        assert db_session.get(Telemetry, sentinel_telem.id) is not None
    finally:
        # Clean up sentinels
        db_session.execute(delete(Telemetry).where(Telemetry.id == sentinel_telem.id))
        db_session.execute(delete(Hive).where(Hive.id == sentinel_hive.id))
        db_session.execute(delete(User).where(User.id == sentinel_user.id))
        db_session.commit()


def test_demo_qr_token_security_and_consumer_resolution(db_session: Session) -> None:
    """Verify that raw QR token is never stored in DB, and verification endpoint resolves successfully."""
    result = bootstrap_demo_dataset(db_session, include_blockchain=False)

    raw_token = result.raw_verification_token
    assert len(raw_token) == 64

    # Verify Database QrToken record: ONLY stores token_hash
    qr_record = db_session.get(QrToken, result.qr_token_id)
    assert qr_record is not None
    expected_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest().lower()
    assert qr_record.token_hash == expected_hash
    assert qr_record.status == QrStatus.ACTIVE
    # Proves raw token is NOT in database
    assert not hasattr(qr_record, "raw_token")

    # Verify Public Consumer Verification resolution
    consumer_res = verify_consumer_token(db_session, raw_token)
    assert consumer_res.verification_status == "VERIFIED"
    assert consumer_res.warning is None
    assert consumer_res.batch.batch_code == result.batch_code
    assert consumer_res.packaging_lot.package_lot_code == result.package_lot_code
    assert len(consumer_res.provenance) == 1
    assert any("Kashmir Valley" in r for r in consumer_res.provenance[0].regions)
    assert len(consumer_res.lab_evidence) == 1
    assert consumer_res.lab_evidence[0].certificate_id == result.certificate_id


def test_demo_blockchain_failure_when_unreachable_and_no_mock_fallback(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that bootstrap reports a clear failure if EVM is requested but unreachable, rather than silently mocking."""
    from app.demo import bootstrap as bootstrap_mod

    # Force is_node_online to return False
    monkeypatch.setattr(bootstrap_mod, "is_node_online", lambda rpc_url: False)

    with pytest.raises(RuntimeError, match="not reachable.*Silent fallback to mock is prohibited"):
        bootstrap_demo_dataset(db_session, include_blockchain=True)


def test_demo_live_blockchain_execution_when_node_available(db_session: Session) -> None:
    """Verify real EVM on-chain transaction execution and PostgreSQL recording when node is online."""
    if not is_node_online("http://127.0.0.1:8545"):
        pytest.skip("Local EVM node not running at http://127.0.0.1:8545")

    result = bootstrap_demo_dataset(db_session, include_blockchain=True)

    assert result.blockchain_status.startswith("REAL_LOCAL_EVM_CONFIRMED")
    assert len(result.blockchain_records) == 2
    assert result.blockchain_records[0]["event_type"] == "BATCH_REGISTERED"
    assert result.blockchain_records[0]["status"] == "CONFIRMED"
    assert result.blockchain_records[0]["transaction_hash"].startswith("0x")
    assert result.blockchain_records[1]["event_type"] == "LAB_EVIDENCE_RECORDED"
    assert result.blockchain_records[1]["status"] == "CONFIRMED"
    assert result.blockchain_records[1]["transaction_hash"].startswith("0x")

    # Verify PostgreSQL BlockchainRecord rows
    records = db_session.scalars(
        select(BlockchainRecord).where(BlockchainRecord.batch_id == result.batch_id)
    ).all()
    assert len(records) == 2
