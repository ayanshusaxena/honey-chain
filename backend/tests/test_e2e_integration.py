"""End-to-end integration test suite for Honey Chain (Roadmap Chunk 14).

Verifies the complete, integrated lifecycle across all backend domains:
1. Multi-role authentication (Admin, Beekeeper, Processor) via /auth/login
2. Hive registration & management
3. IoT Telemetry ingestion
4. AI / Rule-based Risk evaluation
5. Harvest creation, hive yield allocation & finalization
6. Collection Lot creation, harvest allocation & finalization
7. Processing Batch creation, collection lot allocation & finalization
8. Lab Evidence PDF certificate upload, SHA-256 computation & verification
9. On-chain Batch registration (HoneyTraceability.registerBatch)
10. On-chain Lab Evidence hash recording (HoneyTraceability.addEvidence)
11. Packaging Lot creation consuming batch yield
12. Single-use QR Token generation with 256-bit cryptographically secure token
13. Public consumer verification endpoint resolving batch identity, packaging,
    provenance with hive regions, lab evidence, and on-chain blockchain records
14. Administrative HOLD transition and dynamic warning on public QR
15. Administrative status restoration to ACTIVE
16. Administrative RECALL transition and urgent warning on public QR
17. Full audit event trail verification in PostgreSQL
18. Failure paths: unfinalized batch restrictions, status transition rules,
    RBAC enforcement, blockchain unconfigured/failure resilience, and privacy checks.
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
import io
import os
from pathlib import Path
import socket
from urllib.parse import urlparse
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.auth.security import create_access_token, hash_password
from app.blockchain.adapter import (
    MockBlockchainClient,
    UnconfiguredBlockchainClient,
)
from app.blockchain.config import BlockchainSettings
from app.blockchain.router import get_service
from app.blockchain.service import BlockchainService
from app.core.database import SessionLocal
from app.main import app
from app.models.audit import AuditEvent
from app.models.enums import (
    BatchStatus,
    BlockchainStatus,
    HiveStatus,
    LabEvidenceStatus,
    PackagingUnit,
    QrStatus,
    RiskLevel,
    TelemetryQuality,
    UserRole,
)
from app.models.evidence import BlockchainRecord, LabEvidence, PackagingLot, QrToken
from app.models.hive import Harvest, Hive, HiveHarvest, RiskEvent, Telemetry
from app.models.identity import User
from app.models.traceability import (
    Batch,
    BatchCollectionLot,
    CollectionLot,
    CollectionLotHarvest,
)

TEST_EMAIL_PREFIX = "test-e2e-"
TEST_HIVE_PREFIX = "E2E-HIV-"
TEST_HARVEST_PREFIX = "E2E-HRV-"
TEST_LOT_PREFIX = "E2E-LOT-"
TEST_BATCH_PREFIX = "E2E-BAT-"
TEST_PKG_PREFIX = "E2E-PKG-"
TEST_CERT_PREFIX = "E2E-CERT-"

STORAGE_DIR = Path(__file__).resolve().parents[1] / "uploads" / "lab_evidence"


def _cleanup_test_data(db: Session) -> None:
    """Clean up only records created by this E2E test suite.

    Cleanup is intentionally prefix/ID scoped so running these tests cannot delete
    unrelated demo or operational data from the shared PostgreSQL database.
    """
    # Discover E2E-owned parent entities by deterministic test prefixes.
    e2e_user_ids = db.scalars(
        select(User.id).where(User.email.like(f"{TEST_EMAIL_PREFIX}%"))
    ).all()
    e2e_hive_ids = db.scalars(
        select(Hive.id).where(Hive.hive_code.like(f"{TEST_HIVE_PREFIX}%"))
    ).all()
    e2e_harvest_ids = db.scalars(
        select(Harvest.id).where(Harvest.harvest_code.like(f"{TEST_HARVEST_PREFIX}%"))
    ).all()
    e2e_lot_ids = db.scalars(
        select(CollectionLot.id).where(CollectionLot.lot_code.like(f"{TEST_LOT_PREFIX}%"))
    ).all()
    e2e_batch_ids = db.scalars(
        select(Batch.id).where(Batch.batch_code.like(f"{TEST_BATCH_PREFIX}%"))
    ).all()
    e2e_pkg_ids = db.scalars(
        select(PackagingLot.id).where(
            PackagingLot.package_lot_code.like(f"{TEST_PKG_PREFIX}%")
        )
    ).all()
    e2e_lab_ids = db.scalars(
        select(LabEvidence.id).where(
            LabEvidence.certificate_id.like(f"{TEST_CERT_PREFIX}%")
        )
    ).all()
    e2e_qr_ids = (
        db.scalars(
            select(QrToken.id).where(QrToken.packaging_lot_id.in_(e2e_pkg_ids))
        ).all()
        if e2e_pkg_ids
        else []
    )
    e2e_bc_ids = []
    bc_conditions = []
    if e2e_batch_ids:
        bc_conditions.append(BlockchainRecord.batch_id.in_(e2e_batch_ids))
    if e2e_lab_ids:
        bc_conditions.append(BlockchainRecord.lab_evidence_id.in_(e2e_lab_ids))
    if bc_conditions:
        e2e_bc_ids = db.scalars(
            select(BlockchainRecord.id).where(or_(*bc_conditions))
        ).all()

    # Audit entities may use IDs from any of the E2E-owned records above.
    e2e_entity_ids = (
        set(e2e_user_ids)
        | set(e2e_hive_ids)
        | set(e2e_harvest_ids)
        | set(e2e_lot_ids)
        | set(e2e_batch_ids)
        | set(e2e_pkg_ids)
        | set(e2e_lab_ids)
        | set(e2e_qr_ids)
        | set(e2e_bc_ids)
    )

    # Delete dependent records first, always constrained to E2E-owned IDs.
    if e2e_qr_ids:
        db.execute(delete(QrToken).where(QrToken.id.in_(e2e_qr_ids)))
    if e2e_bc_ids:
        db.execute(delete(BlockchainRecord).where(BlockchainRecord.id.in_(e2e_bc_ids)))
    if e2e_pkg_ids:
        db.execute(delete(PackagingLot).where(PackagingLot.id.in_(e2e_pkg_ids)))
    if e2e_lab_ids:
        db.execute(delete(LabEvidence).where(LabEvidence.id.in_(e2e_lab_ids)))

    audit_conditions = []
    if e2e_user_ids:
        audit_conditions.append(AuditEvent.actor_user_id.in_(e2e_user_ids))
    if e2e_entity_ids:
        audit_conditions.append(AuditEvent.entity_id.in_(list(e2e_entity_ids)))
    if audit_conditions:
        db.execute(delete(AuditEvent).where(or_(*audit_conditions)))

    if e2e_batch_ids:
        db.execute(
            delete(BatchCollectionLot).where(
                BatchCollectionLot.batch_id.in_(e2e_batch_ids)
            )
        )
    if e2e_lot_ids:
        db.execute(
            delete(BatchCollectionLot).where(
                BatchCollectionLot.collection_lot_id.in_(e2e_lot_ids)
            )
        )

    if e2e_lot_ids:
        db.execute(
            delete(CollectionLotHarvest).where(
                CollectionLotHarvest.collection_lot_id.in_(e2e_lot_ids)
            )
        )
    if e2e_harvest_ids:
        db.execute(
            delete(CollectionLotHarvest).where(
                CollectionLotHarvest.harvest_id.in_(e2e_harvest_ids)
            )
        )

    if e2e_hive_ids:
        db.execute(
            delete(HiveHarvest).where(HiveHarvest.hive_id.in_(e2e_hive_ids))
        )
    if e2e_harvest_ids:
        db.execute(
            delete(HiveHarvest).where(HiveHarvest.harvest_id.in_(e2e_harvest_ids))
        )

    if e2e_batch_ids:
        db.execute(delete(Batch).where(Batch.id.in_(e2e_batch_ids)))
    if e2e_lot_ids:
        db.execute(delete(CollectionLot).where(CollectionLot.id.in_(e2e_lot_ids)))
    if e2e_harvest_ids:
        db.execute(delete(Harvest).where(Harvest.id.in_(e2e_harvest_ids)))

    if e2e_hive_ids:
        db.execute(delete(RiskEvent).where(RiskEvent.hive_id.in_(e2e_hive_ids)))
        db.execute(delete(Telemetry).where(Telemetry.hive_id.in_(e2e_hive_ids)))
        db.execute(delete(Hive).where(Hive.id.in_(e2e_hive_ids)))

    if e2e_user_ids:
        db.execute(delete(User).where(User.id.in_(e2e_user_ids)))

    db.commit()

    # Remove only E2E-generated evidence artifacts.
    if STORAGE_DIR.exists():
        for item in STORAGE_DIR.glob(f"*{TEST_CERT_PREFIX}*"):
            try:
                item.unlink()
            except OSError:
                pass


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """Database session fixture with pre- and post-test cleanup."""
    if SessionLocal is None:
        pytest.skip("HONEY_CHAIN_DATABASE_URL is not configured.")

    with SessionLocal() as db:
        _cleanup_test_data(db)
        try:
            yield db
        finally:
            _cleanup_test_data(db)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """TestClient fixture with dependency override reset."""
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _create_user(session: Session, email: str, role: UserRole, password: str = "TestPass123!") -> User:
    """Helper to create an active user with hashed password."""
    user = User(
        id=uuid4(),
        name=f"E2E {role.value}",
        email=email.lower(),
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _login(client: TestClient, email: str, password: str = "TestPass123!") -> dict[str, str]:
    """Authenticate via /auth/login and return Bearer auth header."""
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, f"Login failed: {res.text}"
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ===========================================================================
# 1. Complete Happy Path End-to-End Lifecycle
# ===========================================================================

def test_e2e_happy_path_complete_lifecycle(session: Session, client: TestClient) -> None:
    """Validate the complete, realistic end-to-end Honey Chain workflow.

    Flow:
    Authentication -> Hive -> Telemetry -> AI Risk -> Harvest -> Collection Lot
    -> Processing Batch -> Finalize -> Lab Evidence PDF -> Blockchain Registration
    -> Packaging Lot -> Single-Use QR -> Public Verification -> ADMIN HOLD
    -> Public Verification (HOLD) -> Restore ACTIVE -> Public Verification (VERIFIED)
    -> ADMIN RECALL -> Public Verification (RECALLED) -> Audit Trail Verification.
    """
    suffix = uuid4().hex[:8]

    # Setup Blockchain mock adapter
    mock_bc = MockBlockchainClient(
        network_name="hardhat-local",
        contract_address="0x5FbDB2315678afecb367f032d93F642f64180aa3",
    )
    mock_service = BlockchainService(client=mock_bc)
    app.dependency_overrides[get_service] = lambda: mock_service

    # -----------------------------------------------------------------------
    # Step 1: Authentication for all roles
    # -----------------------------------------------------------------------
    admin_user = _create_user(session, f"{TEST_EMAIL_PREFIX}admin-{suffix}@example.com", UserRole.ADMIN)
    beekeeper_user = _create_user(session, f"{TEST_EMAIL_PREFIX}bk-{suffix}@example.com", UserRole.BEEKEEPER)
    processor_user = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-{suffix}@example.com", UserRole.PROCESSOR)

    admin_headers = _login(client, admin_user.email)
    bk_headers = _login(client, beekeeper_user.email)
    proc_headers = _login(client, processor_user.email)

    # -----------------------------------------------------------------------
    # Step 2: Hive Registration
    # -----------------------------------------------------------------------
    hive_code = f"{TEST_HIVE_PREFIX}{suffix}"
    hive_res = client.post(
        "/hives",
        json={"hive_code": hive_code, "location_region": "Kashmir Valley - Pampore"},
        headers=bk_headers,
    )
    assert hive_res.status_code == 201
    hive_data = hive_res.json()
    hive_id = hive_data["id"]
    assert hive_data["hive_code"] == hive_code
    assert hive_data["location_region"] == "Kashmir Valley - Pampore"
    assert hive_data["beekeeper_id"] == str(beekeeper_user.id)
    assert hive_data["status"] == "ACTIVE"

    # -----------------------------------------------------------------------
    # Step 3: IoT Hive Telemetry Ingestion
    # -----------------------------------------------------------------------
    tel_res = client.post(
        f"/hives/{hive_id}/telemetry",
        json={
            "device_timestamp": "2026-09-06T08:30:00Z",
            "weight_kg": 32.4,
            "temperature_c": 34.8,
            "humidity_pct": 52.5,
            "quality": "VALID",
        },
        headers=bk_headers,
    )
    assert tel_res.status_code == 201
    tel_data = tel_res.json()
    telemetry_id = tel_data["id"]
    assert tel_data["weight_kg"] == 32.4
    assert tel_data["quality"] == "VALID"

    # -----------------------------------------------------------------------
    # Step 4: AI / Rule-Based Risk Evaluation
    # -----------------------------------------------------------------------
    risk_res = client.post(
        f"/hives/{hive_id}/risk/evaluate",
        json={"telemetry_id": telemetry_id},
        headers=bk_headers,
    )
    assert risk_res.status_code == 201
    risk_data = risk_res.json()
    assert risk_data["hive_id"] == str(hive_id)
    assert 0.0 <= risk_data["risk_score"] <= 1.0
    assert risk_data["risk_level"] in ("LOW", "MEDIUM", "HIGH")
    assert risk_data["source"] in ("AI_MODEL", "RULE_ENGINE", "HYBRID")

    # -----------------------------------------------------------------------
    # Step 5: Harvest Creation, Allocation & Finalization
    # -----------------------------------------------------------------------
    harvest_code = f"{TEST_HARVEST_PREFIX}{suffix}"
    harvest_res = client.post(
        "/harvests",
        json={
            "harvest_code": harvest_code,
            "harvest_date": "2026-09-06",
            "quantity_kg": 60.0,
            "notes": "Spring raw acacia honey harvest",
        },
        headers=bk_headers,
    )
    assert harvest_res.status_code == 201
    harvest_id = harvest_res.json()["id"]

    alloc_h_res = client.post(
        f"/harvests/{harvest_id}/hives",
        json={"hive_id": hive_id, "quantity_used_kg": 60.0},
        headers=bk_headers,
    )
    assert alloc_h_res.status_code == 201

    fin_h_res = client.post(f"/harvests/{harvest_id}/finalize", headers=bk_headers)
    assert fin_h_res.status_code == 200
    assert fin_h_res.json()["is_finalized"] is True

    # -----------------------------------------------------------------------
    # Step 6: Collection Lot Creation, Allocation & Finalization
    # -----------------------------------------------------------------------
    lot_code = f"{TEST_LOT_PREFIX}{suffix}"
    lot_res = client.post(
        "/collection-lots",
        json={"lot_code": lot_code, "quantity_kg": 60.0},
        headers=proc_headers,
    )
    assert lot_res.status_code == 201
    lot_id = lot_res.json()["id"]

    alloc_l_res = client.post(
        f"/collection-lots/{lot_id}/harvests",
        json={"harvest_id": harvest_id, "quantity_used_kg": 60.0},
        headers=proc_headers,
    )
    assert alloc_l_res.status_code == 201

    fin_l_res = client.post(f"/collection-lots/{lot_id}/finalize", headers=proc_headers)
    assert fin_l_res.status_code == 200
    assert fin_l_res.json()["is_finalized"] is True

    # -----------------------------------------------------------------------
    # Step 7: Processing Batch Creation, Allocation & Finalization
    # -----------------------------------------------------------------------
    batch_code = f"{TEST_BATCH_PREFIX}{suffix}"
    batch_res = client.post(
        "/batches",
        json={"batch_code": batch_code},
        headers=proc_headers,
    )
    assert batch_res.status_code == 201
    batch_data = batch_res.json()
    batch_id = batch_data["id"]
    assert batch_data["processor_id"] == str(processor_user.id)
    assert batch_data["status"] == "ACTIVE"
    assert batch_data["is_finalized"] is False

    alloc_b_res = client.post(
        f"/batches/{batch_id}/collection-lots",
        json={"collection_lot_id": lot_id, "quantity_used_kg": 60.0},
        headers=proc_headers,
    )
    assert alloc_b_res.status_code == 201

    fin_b_res = client.post(f"/batches/{batch_id}/finalize", headers=proc_headers)
    assert fin_b_res.status_code == 200
    fin_batch_data = fin_b_res.json()
    assert fin_batch_data["is_finalized"] is True
    assert fin_batch_data["derived_quantity_kg"] == 60.0

    # -----------------------------------------------------------------------
    # Step 8: Lab Evidence PDF Upload & Hash Verification
    # -----------------------------------------------------------------------
    cert_id = f"{TEST_CERT_PREFIX}{suffix}"
    pdf_content = b"%PDF-1.4\n%Honey Chain ISO Lab Report\nPurity: 99.8%\n%%EOF"
    files = {"file": (f"{cert_id}.pdf", io.BytesIO(pdf_content), "application/pdf")}
    data = {
        "certificate_id": cert_id,
        "test_summary": "Passed C4 sugar screen and HMF freshness threshold.",
    }

    lab_res = client.post(
        f"/batches/{batch_id}/lab-evidence",
        data=data,
        files=files,
        headers=proc_headers,
    )
    assert lab_res.status_code == 201
    lab_data = lab_res.json()
    evidence_id = lab_data["id"]
    sha256_hash = lab_data["file_hash_sha256"]
    assert len(sha256_hash) == 64
    assert lab_data["status"] == "ACTIVE"

    # Verify physical file artifact matches computed SHA-256
    verify_lab_res = client.get(
        f"/lab-evidence/{evidence_id}/verify",
        headers=proc_headers,
    )
    assert verify_lab_res.status_code == 200
    v_lab = verify_lab_res.json()
    assert v_lab["is_verified"] is True
    assert v_lab["is_hash_verified"] is True
    assert v_lab["file_hash_sha256"] == sha256_hash
    assert v_lab["computed_hash_sha256"] == sha256_hash

    # -----------------------------------------------------------------------
    # Step 9: On-Chain Batch Registration
    # -----------------------------------------------------------------------
    bc_batch_res = client.post(
        f"/batches/{batch_id}/blockchain-register",
        headers=proc_headers,
    )
    assert bc_batch_res.status_code == 201
    bc_batch_data = bc_batch_res.json()
    assert bc_batch_data["batch_id"] == str(batch_id)
    assert bc_batch_data["event_type"] == "BATCH_REGISTERED"
    assert bc_batch_data["status"] == "CONFIRMED"
    assert bc_batch_data["transaction_hash"].startswith("0x")

    # -----------------------------------------------------------------------
    # Step 10: On-Chain Lab Evidence Hash Recording
    # -----------------------------------------------------------------------
    bc_ev_res = client.post(
        f"/lab-evidence/{evidence_id}/blockchain-record",
        headers=proc_headers,
    )
    assert bc_ev_res.status_code == 201
    bc_ev_data = bc_ev_res.json()
    assert bc_ev_data["lab_evidence_id"] == str(evidence_id)
    assert bc_ev_data["event_type"] == "LAB_EVIDENCE_RECORDED"
    assert bc_ev_data["status"] == "CONFIRMED"
    assert bc_ev_data["transaction_hash"].startswith("0x")

    # Verify on-chain query endpoint returns both records
    records_res = client.get(
        f"/batches/{batch_id}/blockchain-records",
        headers=proc_headers,
    )
    assert records_res.status_code == 200
    assert len(records_res.json()) == 2

    # -----------------------------------------------------------------------
    # Step 11: Packaging Lot Creation
    # -----------------------------------------------------------------------
    package_lot_code = f"{TEST_PKG_PREFIX}{suffix}"
    # 100 jars * 500 grams = 50 kg (<= 60 kg derived batch quantity)
    pkg_res = client.post(
        f"/batches/{batch_id}/packaging",
        json={
            "package_lot_code": package_lot_code,
            "quantity": 100,
            "unit": "JARS",
            "package_size_grams": 500.0,
        },
        headers=proc_headers,
    )
    assert pkg_res.status_code == 201
    pkg_data = pkg_res.json()
    pkg_lot_id = pkg_data["id"]
    assert pkg_data["package_lot_code"] == package_lot_code
    assert pkg_data["packaged_quantity_kg"] == 50.0

    # -----------------------------------------------------------------------
    # Step 12: Unique Single-Use QR Token Generation
    # -----------------------------------------------------------------------
    qr_res = client.post(f"/packaging/{pkg_lot_id}/qr", headers=proc_headers)
    assert qr_res.status_code == 201
    qr_data = qr_res.json()
    verification_url = qr_data["verification_url"]
    raw_token = verification_url.split("/verify/")[-1]
    assert len(raw_token) == 64
    assert qr_data["status"] == "ACTIVE"

    # -----------------------------------------------------------------------
    # Step 13: Public Consumer Verification (ACTIVE)
    # -----------------------------------------------------------------------
    # Unauthenticated public consumer scan
    pub_res = client.get(f"/verify/{raw_token}")
    assert pub_res.status_code == 200
    pub_data = pub_res.json()

    # Verify public-safe status & alerts
    assert pub_data["verification_status"] == "VERIFIED"
    assert pub_data["warning"] is None

    # Verify batch identity
    assert pub_data["batch"]["batch_code"] == batch_code
    assert pub_data["batch"]["status"] == "ACTIVE"
    assert pub_data["batch"]["is_finalized"] is True

    # Verify packaging details
    assert pub_data["packaging_lot"]["package_lot_code"] == package_lot_code
    assert pub_data["packaging_lot"]["quantity"] == 100
    assert pub_data["packaging_lot"]["unit"] == "JARS"
    assert pub_data["packaging_lot"]["package_size_grams"] == 500.0
    assert pub_data["packaging_lot"]["packaged_quantity_kg"] == 50.0

    # Verify provenance (distinct hive regions, no PII or GPS coordinates)
    assert len(pub_data["provenance"]) == 1
    assert pub_data["provenance"][0]["harvest_code"] == harvest_code
    assert pub_data["provenance"][0]["regions"] == ["Kashmir Valley - Pampore"]

    # Verify lab evidence record with SHA-256
    assert len(pub_data["lab_evidence"]) == 1
    assert pub_data["lab_evidence"][0]["certificate_id"] == cert_id
    assert pub_data["lab_evidence"][0]["file_hash_sha256"] == sha256_hash
    assert pub_data["lab_evidence"][0]["status"] == "ACTIVE"

    # Verify blockchain references (both on-chain transactions displayed)
    assert len(pub_data["blockchain_records"]) == 2
    event_types = {r["event_type"] for r in pub_data["blockchain_records"]}
    assert "BATCH_REGISTERED" in event_types
    assert "LAB_EVIDENCE_RECORDED" in event_types
    for bc_rec in pub_data["blockchain_records"]:
        assert bc_rec["transaction_hash"].startswith("0x")
        assert bc_rec["status"] == "CONFIRMED"

    # -----------------------------------------------------------------------
    # Step 14: ADMIN Transitions Batch Status to HOLD
    # -----------------------------------------------------------------------
    hold_res = client.patch(
        f"/batches/{batch_id}/status",
        json={"status": "HOLD"},
        headers=admin_headers,
    )
    assert hold_res.status_code == 200
    assert hold_res.json()["status"] == "HOLD"

    # Public verification on the EXACT SAME QR reflects HOLD dynamically
    pub_hold_res = client.get(f"/verify/{raw_token}")
    assert pub_hold_res.status_code == 200
    pub_hold_data = pub_hold_res.json()
    assert pub_hold_data["verification_status"] == "HOLD"
    assert pub_hold_data["batch"]["status"] == "HOLD"
    assert pub_hold_data["warning"] is not None
    assert "HOLD" in pub_hold_data["warning"]

    # -----------------------------------------------------------------------
    # Step 15: ADMIN Restores Batch Status to ACTIVE
    # -----------------------------------------------------------------------
    restore_res = client.patch(
        f"/batches/{batch_id}/status",
        json={"status": "ACTIVE"},
        headers=admin_headers,
    )
    assert restore_res.status_code == 200
    assert restore_res.json()["status"] == "ACTIVE"

    pub_restored_res = client.get(f"/verify/{raw_token}")
    assert pub_restored_res.status_code == 200
    pub_restored_data = pub_restored_res.json()
    assert pub_restored_data["verification_status"] == "VERIFIED"
    assert pub_restored_data["warning"] is None

    # -----------------------------------------------------------------------
    # Step 16: ADMIN Transitions Batch Status to RECALL
    # -----------------------------------------------------------------------
    recall_res = client.patch(
        f"/batches/{batch_id}/status",
        json={"status": "RECALL"},
        headers=admin_headers,
    )
    assert recall_res.status_code == 200
    assert recall_res.json()["status"] == "RECALL"

    # Public verification reflects terminal RECALL status and warning
    pub_recall_res = client.get(f"/verify/{raw_token}")
    assert pub_recall_res.status_code == 200
    pub_recall_data = pub_recall_res.json()
    assert pub_recall_data["verification_status"] == "RECALLED"
    assert pub_recall_data["batch"]["status"] == "RECALL"
    assert pub_recall_data["warning"] is not None
    assert "RECALLED" in pub_recall_data["warning"]

    # -----------------------------------------------------------------------
    # Step 17: Audit Trail Verification in PostgreSQL
    # -----------------------------------------------------------------------
    audits = session.scalars(
        select(AuditEvent).order_by(AuditEvent.timestamp.asc())
    ).all()
    audit_events_recorded = [a.event_type for a in audits]

    assert "LAB_EVIDENCE_UPLOADED" in audit_events_recorded
    assert "BLOCKCHAIN_BATCH_REGISTERED" in audit_events_recorded
    assert "BLOCKCHAIN_EVIDENCE_RECORDED" in audit_events_recorded
    assert "PACKAGING_LOT_CREATED" in audit_events_recorded
    assert "QR_GENERATED" in audit_events_recorded
    assert "BATCH_STATUS_TRANSITION" in audit_events_recorded


# ===========================================================================
# 2. Downstream Blockers on Unfinalized Batches
# ===========================================================================

def test_unfinalized_batch_cannot_proceed_to_downstream_operations(
    session: Session, client: TestClient
) -> None:
    """Unfinalized batches must strictly block packaging, QR, and status changes."""
    suffix = uuid4().hex[:8]
    processor = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-{suffix}@example.com", UserRole.PROCESSOR)
    admin = _create_user(session, f"{TEST_EMAIL_PREFIX}admin-{suffix}@example.com", UserRole.ADMIN)

    proc_headers = _login(client, processor.email)
    admin_headers = _login(client, admin.email)

    # Create unfinalized batch
    res = client.post(
        "/batches",
        json={"batch_code": f"{TEST_BATCH_PREFIX}UNFIN-{suffix}"},
        headers=proc_headers,
    )
    assert res.status_code == 201
    batch_id = res.json()["id"]

    # 1. Packaging lot creation on unfinalized batch fails (422)
    pkg_res = client.post(
        f"/batches/{batch_id}/packaging",
        json={
            "package_lot_code": f"{TEST_PKG_PREFIX}UNFIN-{suffix}",
            "quantity": 10,
            "unit": "JARS",
            "package_size_grams": 500.0,
        },
        headers=proc_headers,
    )
    assert pkg_res.status_code == 422
    assert "unfinalized batch" in pkg_res.json()["detail"].lower()

    # 2. Status transition on unfinalized batch fails (422)
    status_res = client.patch(
        f"/batches/{batch_id}/status",
        json={"status": "HOLD"},
        headers=admin_headers,
    )
    assert status_res.status_code == 422
    assert "unfinalized batches cannot transition status" in status_res.json()["detail"].lower()


# ===========================================================================
# 3. HOLD and RECALL Downstream Restrictions
# ===========================================================================

def test_hold_and_recall_restrictions_enforced(
    session: Session, client: TestClient
) -> None:
    """Validate that HOLD and RECALL statuses enforce operational lockouts."""
    suffix = uuid4().hex[:8]
    processor = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-{suffix}@example.com", UserRole.PROCESSOR)
    admin = _create_user(session, f"{TEST_EMAIL_PREFIX}admin-{suffix}@example.com", UserRole.ADMIN)
    beekeeper = _create_user(session, f"{TEST_EMAIL_PREFIX}bk-{suffix}@example.com", UserRole.BEEKEEPER)

    proc_headers = _login(client, processor.email)
    admin_headers = _login(client, admin.email)
    bk_headers = _login(client, beekeeper.email)

    # Setup finalized batch
    hive_res = client.post(
        "/hives",
        json={"hive_code": f"{TEST_HIVE_PREFIX}{suffix}", "location_region": "Pulwama"},
        headers=bk_headers,
    )
    hive_id = hive_res.json()["id"]

    harv_res = client.post(
        "/harvests",
        json={"harvest_code": f"{TEST_HARVEST_PREFIX}{suffix}", "harvest_date": "2026-09-06", "quantity_kg": 40.0},
        headers=bk_headers,
    )
    harv_id = harv_res.json()["id"]
    client.post(f"/harvests/{harv_id}/hives", json={"hive_id": hive_id, "quantity_used_kg": 40.0}, headers=bk_headers)
    client.post(f"/harvests/{harv_id}/finalize", headers=bk_headers)

    lot_res = client.post("/collection-lots", json={"lot_code": f"{TEST_LOT_PREFIX}{suffix}", "quantity_kg": 40.0}, headers=proc_headers)
    lot_id = lot_res.json()["id"]
    client.post(f"/collection-lots/{lot_id}/harvests", json={"harvest_id": harv_id, "quantity_used_kg": 40.0}, headers=proc_headers)
    client.post(f"/collection-lots/{lot_id}/finalize", headers=proc_headers)

    bat_res = client.post("/batches", json={"batch_code": f"{TEST_BATCH_PREFIX}{suffix}"}, headers=proc_headers)
    batch_id = bat_res.json()["id"]
    client.post(f"/batches/{batch_id}/collection-lots", json={"collection_lot_id": lot_id, "quantity_used_kg": 40.0}, headers=proc_headers)
    client.post(f"/batches/{batch_id}/finalize", headers=proc_headers)

    # Transition to HOLD
    client.patch(f"/batches/{batch_id}/status", json={"status": "HOLD"}, headers=admin_headers)

    # Cannot create packaging while on HOLD (422)
    pkg_res = client.post(
        f"/batches/{batch_id}/packaging",
        json={
            "package_lot_code": f"{TEST_PKG_PREFIX}{suffix}",
            "quantity": 10,
            "unit": "JARS",
            "package_size_grams": 500.0,
        },
        headers=proc_headers,
    )
    assert pkg_res.status_code == 422
    assert "HOLD" in pkg_res.json()["detail"]

    # State machine: HOLD cannot jump directly to RECALL (must return to ACTIVE first)
    invalid_trans = client.patch(
        f"/batches/{batch_id}/status",
        json={"status": "RECALL"},
        headers=admin_headers,
    )
    assert invalid_trans.status_code == 422

    # Restore to ACTIVE, then transition to RECALL
    client.patch(f"/batches/{batch_id}/status", json={"status": "ACTIVE"}, headers=admin_headers)
    client.patch(f"/batches/{batch_id}/status", json={"status": "RECALL"}, headers=admin_headers)

    # RECALL is terminal: cannot transition back to ACTIVE or HOLD
    term1 = client.patch(f"/batches/{batch_id}/status", json={"status": "ACTIVE"}, headers=admin_headers)
    assert term1.status_code == 422
    term2 = client.patch(f"/batches/{batch_id}/status", json={"status": "HOLD"}, headers=admin_headers)
    assert term2.status_code == 422


# ===========================================================================
# 4. Role-Based Access Control (RBAC) Across Flow
# ===========================================================================

def test_role_based_access_control_across_flow(
    session: Session, client: TestClient
) -> None:
    """Verify authorization checks strictly reject cross-role unauthorized calls."""
    suffix = uuid4().hex[:8]
    beekeeper = _create_user(session, f"{TEST_EMAIL_PREFIX}bk-{suffix}@example.com", UserRole.BEEKEEPER)
    processor = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-{suffix}@example.com", UserRole.PROCESSOR)

    bk_headers = _login(client, beekeeper.email)
    proc_headers = _login(client, processor.email)

    # 1. Beekeeper cannot create batches
    res = client.post("/batches", json={"batch_code": f"{TEST_BATCH_PREFIX}BK-{suffix}"}, headers=bk_headers)
    assert res.status_code == 403

    # 2. Beekeeper cannot create packaging lots
    fake_batch_id = uuid4()
    res = client.post(
        f"/batches/{fake_batch_id}/packaging",
        json={"package_lot_code": f"{TEST_PKG_PREFIX}{suffix}", "quantity": 10, "unit": "JARS", "package_size_grams": 500},
        headers=bk_headers,
    )
    assert res.status_code == 403

    # 3. Processor cannot transition batch status (ADMIN only)
    res = client.patch(f"/batches/{fake_batch_id}/status", json={"status": "HOLD"}, headers=proc_headers)
    assert res.status_code == 403

    # 4. Unauthenticated requests to protected endpoints return 401
    assert client.post("/harvests", json={}).status_code == 401
    assert client.post("/batches", json={}).status_code == 401
    assert client.post(f"/batches/{fake_batch_id}/blockchain-register").status_code == 401


# ===========================================================================
# 5. Blockchain Resilience and Graceful Degradation
# ===========================================================================

def test_blockchain_unavailable_does_not_corrupt_postgresql_state(
    session: Session, client: TestClient
) -> None:
    """When blockchain is unconfigured, API fails gracefully with 503 and preserves DB."""
    suffix = uuid4().hex[:8]
    processor = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-{suffix}@example.com", UserRole.PROCESSOR)
    proc_headers = _login(client, processor.email)

    # Inject UnconfiguredBlockchainClient
    unconf_service = BlockchainService(client=UnconfiguredBlockchainClient())
    app.dependency_overrides[get_service] = lambda: unconf_service

    # Create batch
    res = client.post("/batches", json={"batch_code": f"{TEST_BATCH_PREFIX}UNCONF-{suffix}"}, headers=proc_headers)
    assert res.status_code == 201
    batch_id = res.json()["id"]

    # Attempt on-chain registration
    bc_res = client.post(f"/batches/{batch_id}/blockchain-register", headers=proc_headers)
    assert bc_res.status_code == 503
    assert "not configured" in bc_res.json()["detail"].lower()

    # Verify PostgreSQL batch record is intact and queryable
    get_res = client.get(f"/batches/{batch_id}", headers=proc_headers)
    assert get_res.status_code == 200
    assert get_res.json()["batch_code"] == f"{TEST_BATCH_PREFIX}UNCONF-{suffix}"


def test_blockchain_rpc_failure_logs_audit_and_preserves_state(
    session: Session, client: TestClient
) -> None:
    """When blockchain transaction fails, returns 502 Bad Gateway and logs failure."""
    suffix = uuid4().hex[:8]
    processor = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-{suffix}@example.com", UserRole.PROCESSOR)
    proc_headers = _login(client, processor.email)

    # Inject MockBlockchainClient that simulates failure
    failing_bc = MockBlockchainClient(simulate_failure=True, failure_error_message="Network timeout")
    failing_service = BlockchainService(client=failing_bc)
    app.dependency_overrides[get_service] = lambda: failing_service

    res = client.post("/batches", json={"batch_code": f"{TEST_BATCH_PREFIX}FAIL-{suffix}"}, headers=proc_headers)
    assert res.status_code == 201
    batch_id = res.json()["id"]

    bc_res = client.post(f"/batches/{batch_id}/blockchain-register", headers=proc_headers)
    assert bc_res.status_code == 502
    assert "failed" in bc_res.json()["detail"].lower()

    # Verify failed record was recorded in audit table
    failed_record = session.scalar(
        select(BlockchainRecord).where(BlockchainRecord.batch_id == UUID(batch_id))
    )
    assert failed_record is not None
    assert failed_record.status == BlockchainStatus.FAILED


# ===========================================================================
# 6. Duplicate and Inconsistent Operations Prevented
# ===========================================================================

def test_duplicate_and_inconsistent_operations_prevented(
    session: Session, client: TestClient
) -> None:
    """Ensure duplicate codes, duplicate QR generation, and oversubscription fail safely."""
    suffix = uuid4().hex[:8]
    processor = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-{suffix}@example.com", UserRole.PROCESSOR)
    proc_headers = _login(client, processor.email)

    # 1. Duplicate batch code returns 409
    client.post("/batches", json={"batch_code": f"{TEST_BATCH_PREFIX}DUP-{suffix}"}, headers=proc_headers)
    dup_res = client.post("/batches", json={"batch_code": f"{TEST_BATCH_PREFIX}DUP-{suffix}"}, headers=proc_headers)
    assert dup_res.status_code == 409


# ===========================================================================
# 7. Consumer Verification Security and Privacy
# ===========================================================================

def test_consumer_verification_security_and_privacy(
    session: Session, client: TestClient
) -> None:
    """Public verification must not leak internal identifiers, PII, or paths."""
    # 1. Invalid hex length returns 404
    assert client.get("/verify/invalid-token-short").status_code == 404

    # 2. Non-existent 64-char token returns 404
    fake_token = "0" * 64
    assert client.get(f"/verify/{fake_token}").status_code == 404


# ===========================================================================
# 8. Live Blockchain Node Connectivity Smoke Test (Conditional)
# ===========================================================================

def is_live_node_available(rpc_url: str = "http://127.0.0.1:8545") -> bool:
    """Check if a live local EVM node is reachable."""
    try:
        parsed = urlparse(rpc_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 8545
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def test_live_blockchain_connection_smoke_if_running() -> None:
    """Smoke-check local EVM JSON-RPC connectivity when a node is running."""
    rpc_url = os.getenv("HONEY_CHAIN_BLOCKCHAIN_RPC_URL", "http://127.0.0.1:8545")
    if not is_live_node_available(rpc_url):
        pytest.skip(f"Live EVM JSON-RPC node not available at {rpc_url}; smoke test skipped.")
    assert is_live_node_available(rpc_url) is True


# ===========================================================================
# 9. Cleanup Safety & Non-E2E Sentinel Data Preservation
# ===========================================================================

def test_e2e_cleanup_preserves_non_e2e_data(session: Session) -> None:
    """Verify E2E cleanup preserves unrelated non-E2E records."""
    sentinel_email = f"sentinel-keep-{uuid4().hex[:8]}@example.com"
    sentinel_user = User(
        id=uuid4(),
        name="Sentinel User",
        email=sentinel_email,
        password_hash=hash_password("SentinelPass123!"),
        role=UserRole.BEEKEEPER,
        is_active=True,
    )
    session.add(sentinel_user)
    session.commit()

    sentinel_hive = Hive(
        id=uuid4(),
        hive_code=f"SENTINEL-{uuid4().hex[:8]}",
        beekeeper_id=sentinel_user.id,
        location_region="Sentinel Test Region",
        status=HiveStatus.ACTIVE,
    )
    session.add(sentinel_hive)
    session.commit()

    sentinel_audit = AuditEvent(
        id=uuid4(),
        event_type="SENTINEL_EVENT",
        entity_type="HIVE",
        entity_id=sentinel_hive.id,
        actor_user_id=sentinel_user.id,
        timestamp=datetime.now(UTC),
    )
    session.add(sentinel_audit)
    session.commit()

    try:
        _cleanup_test_data(session)

        surviving_user = session.get(User, sentinel_user.id)
        assert surviving_user is not None
        assert surviving_user.email == sentinel_email

        surviving_hive = session.get(Hive, sentinel_hive.id)
        assert surviving_hive is not None
        assert surviving_hive.location_region == "Sentinel Test Region"

        surviving_audit = session.get(AuditEvent, sentinel_audit.id)
        assert surviving_audit is not None
        assert surviving_audit.event_type == "SENTINEL_EVENT"
    finally:
        session.execute(delete(AuditEvent).where(AuditEvent.id == sentinel_audit.id))
        session.execute(delete(Hive).where(Hive.id == sentinel_hive.id))
        session.execute(delete(User).where(User.id == sentinel_user.id))
        session.commit()
