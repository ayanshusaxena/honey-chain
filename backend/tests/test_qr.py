"""Comprehensive test suite for QR Token lifecycle and Public Consumer Verification."""

from __future__ import annotations

import concurrent.futures
import hashlib
import re
from collections.abc import Generator
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth.security import create_access_token, hash_password
from app.core.config import settings
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
    UserRole,
)
from app.models.evidence import BlockchainRecord, LabEvidence, PackagingLot, QrToken
from app.models.hive import Harvest, Hive, HiveHarvest
from app.models.identity import User
from app.models.traceability import (
    Batch,
    BatchCollectionLot,
    CollectionLot,
    CollectionLotHarvest,
)

TEST_EMAIL_PREFIX = "test-qr-"
TEST_HIVE_PREFIX = "QR-HIV-"
TEST_HARVEST_PREFIX = "QR-HRV-"
TEST_LOT_PREFIX = "QR-LOT-"
TEST_BATCH_PREFIX = "QR-BAT-"
TEST_PACKAGE_LOT_PREFIX = "QR-PKG-"
TEST_CERT_PREFIX = "QR-CERT-"


def _cleanup(database_session: Session) -> None:
    """Clean up test data across tables."""
    # Delete QR tokens and PackagingLots
    database_session.execute(delete(QrToken))
    database_session.execute(
        delete(PackagingLot).where(
            PackagingLot.package_lot_code.like(f"{TEST_PACKAGE_LOT_PREFIX}%")
        )
    )
    database_session.execute(
        delete(LabEvidence).where(
            LabEvidence.certificate_id.like(f"{TEST_CERT_PREFIX}%")
        )
    )
    database_session.execute(delete(BlockchainRecord))

    user_ids = select(User.id).where(User.email.like(f"{TEST_EMAIL_PREFIX}%"))
    database_session.execute(
        delete(AuditEvent).where(AuditEvent.actor_user_id.in_(user_ids))
    )
    database_session.execute(
        delete(AuditEvent).where(AuditEvent.entity_type.in_(["QR_TOKEN", "PACKAGING_LOT", "LAB_EVIDENCE"]))
    )
    database_session.execute(delete(BatchCollectionLot))
    database_session.execute(delete(CollectionLotHarvest))
    database_session.execute(delete(HiveHarvest))
    database_session.execute(
        delete(Batch).where(Batch.batch_code.like(f"{TEST_BATCH_PREFIX}%"))
    )
    database_session.execute(
        delete(CollectionLot).where(CollectionLot.lot_code.like(f"{TEST_LOT_PREFIX}%"))
    )
    database_session.execute(
        delete(Harvest).where(Harvest.harvest_code.like(f"{TEST_HARVEST_PREFIX}%"))
    )
    database_session.execute(
        delete(Hive).where(Hive.hive_code.like(f"{TEST_HIVE_PREFIX}%"))
    )
    database_session.execute(
        delete(User).where(User.email.like(f"{TEST_EMAIL_PREFIX}%"))
    )
    database_session.commit()


@pytest.fixture
def session() -> Generator[Session, None, None]:
    db = SessionLocal()
    _cleanup(db)
    try:
        yield db
    finally:
        _cleanup(db)
        db.close()


def _create_user(session: Session, email: str, role: UserRole) -> User:
    user = User(
        name=f"Test {role.value}",
        email=email.lower(),
        password_hash=hash_password("Password123!"),
        role=role,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def _create_hive(session: Session, hive_code: str, beekeeper: User) -> Hive:
    hive = Hive(
        hive_code=hive_code,
        beekeeper_id=beekeeper.id,
        location_region="Black Forest",
        status=HiveStatus.ACTIVE,
    )
    session.add(hive)
    session.commit()
    session.refresh(hive)
    return hive


def _setup_lineage_and_packaging(
    session: Session,
    beekeeper: User,
    processor: User,
    batch_code: str,
    package_lot_code: str,
    quantity_kg: float = 100.0,
    finalize_batch: bool = True,
    batch_status: BatchStatus = BatchStatus.ACTIVE,
    units: int = 100,
    size_grams: float = 500.0,
) -> tuple[Batch, PackagingLot, Harvest, Hive]:
    """Helper to set up full lineage up to a PackagingLot."""
    unique_suffix = uuid4().hex[:6]
    client = TestClient(app)

    # 1. Hive
    hive = _create_hive(session, f"{TEST_HIVE_PREFIX}{unique_suffix}", beekeeper)

    # 2. Harvest
    res_h = client.post(
        "/harvests",
        headers=_auth_headers(beekeeper),
        json={
            "harvest_code": f"{TEST_HARVEST_PREFIX}{unique_suffix}",
            "harvest_date": str(date.today()),
            "quantity_kg": quantity_kg,
        },
    )
    assert res_h.status_code == 201, res_h.text
    harvest_id = res_h.json()["id"]

    res_h_alloc = client.post(
        f"/harvests/{harvest_id}/hives",
        headers=_auth_headers(beekeeper),
        json={"hive_id": str(hive.id), "quantity_used_kg": quantity_kg},
    )
    assert res_h_alloc.status_code == 201, res_h_alloc.text

    res_h_fin = client.post(
        f"/harvests/{harvest_id}/finalize", headers=_auth_headers(beekeeper)
    )
    assert res_h_fin.status_code == 200, res_h_fin.text

    # 3. Collection Lot
    res_lot = client.post(
        "/collection-lots",
        headers=_auth_headers(processor),
        json={
            "lot_code": f"{TEST_LOT_PREFIX}{unique_suffix}",
            "quantity_kg": quantity_kg,
        },
    )
    assert res_lot.status_code == 201, res_lot.text
    lot_id = res_lot.json()["id"]

    res_lot_alloc = client.post(
        f"/collection-lots/{lot_id}/harvests",
        headers=_auth_headers(processor),
        json={"harvest_id": harvest_id, "quantity_used_kg": quantity_kg},
    )
    assert res_lot_alloc.status_code == 201, res_lot_alloc.text

    res_lot_fin = client.post(
        f"/collection-lots/{lot_id}/finalize", headers=_auth_headers(processor)
    )
    assert res_lot_fin.status_code == 200, res_lot_fin.text

    # 4. Batch
    res_b = client.post(
        "/batches",
        headers=_auth_headers(processor),
        json={"batch_code": batch_code},
    )
    assert res_b.status_code == 201, res_b.text
    batch_id = res_b.json()["id"]

    res_b_alloc = client.post(
        f"/batches/{batch_id}/collection-lots",
        headers=_auth_headers(processor),
        json={"collection_lot_id": lot_id, "quantity_used_kg": quantity_kg},
    )
    assert res_b_alloc.status_code == 201, res_b_alloc.text

    if finalize_batch:
        res_b_fin = client.post(
            f"/batches/{batch_id}/finalize", headers=_auth_headers(processor)
        )
        assert res_b_fin.status_code == 200, res_b_fin.text

    if batch_status != BatchStatus.ACTIVE:
        admin_user = _create_user(
            session,
            f"{TEST_EMAIL_PREFIX}adm-status-{unique_suffix}@example.com",
            UserRole.ADMIN,
        )
        res_b_status = client.patch(
            f"/batches/{batch_id}/status",
            headers=_auth_headers(admin_user),
            json={"status": batch_status.value},
        )
        assert res_b_status.status_code == 200, res_b_status.text

    # 5. Packaging Lot
    res_p = client.post(
        f"/batches/{batch_id}/packaging",
        headers=_auth_headers(processor),
        json={
            "package_lot_code": package_lot_code,
            "quantity": units,
            "unit": PackagingUnit.JARS.value,
            "package_size_grams": size_grams,
        },
    )
    assert res_p.status_code == 201, res_p.text

    session.expire_all()
    batch = session.get(Batch, UUID(batch_id))
    pkg_lot = session.get(PackagingLot, UUID(res_p.json()["id"]))
    harvest = session.get(Harvest, UUID(harvest_id))
    assert batch is not None
    assert pkg_lot is not None
    assert harvest is not None

    return batch, pkg_lot, harvest, hive


# ===========================================================================
# 1. QR Generation & Security
# ===========================================================================

def test_create_qr_success_admin_and_processor(session: Session) -> None:
    """Admin and owning Processor can generate QR token with proper verification URL."""
    client = TestClient(app)
    admin = _create_user(session, f"{TEST_EMAIL_PREFIX}adm-1@example.com", UserRole.ADMIN)
    processor = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-1@example.com", UserRole.PROCESSOR)
    beekeeper = _create_user(session, f"{TEST_EMAIL_PREFIX}bk-1@example.com", UserRole.BEEKEEPER)

    _, lot, _, _ = _setup_lineage_and_packaging(
        session, beekeeper, processor, f"{TEST_BATCH_PREFIX}001", f"{TEST_PACKAGE_LOT_PREFIX}001"
    )

    response = client.post(
        f"/packaging/{lot.id}/qr",
        headers=_auth_headers(processor),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["packaging_lot_id"] == str(lot.id)
    assert data["status"] == "ACTIVE"
    assert "verification_url" in data
    assert data["verification_url"].startswith(f"{settings.public_origin}/verify/")
    raw_token = data["verification_url"].split("/verify/")[-1]
    assert len(raw_token) == 64
    assert re.fullmatch(r"^[0-9a-f]{64}$", raw_token) is not None

    # Verify no secret hashes or raw tokens in model response fields
    assert "token_hash" not in data
    assert "raw_token" not in data

    # Verify DB storage: ONLY token_hash is stored, raw_token is NOT stored
    qr_record = session.scalar(select(QrToken).where(QrToken.packaging_lot_id == lot.id))
    assert qr_record is not None
    expected_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest().lower()
    assert qr_record.token_hash == expected_hash

    # Verify AuditEvent recorded without secrets
    audit_evt = session.scalar(
        select(AuditEvent)
        .where(AuditEvent.entity_type == "QR_TOKEN")
        .where(AuditEvent.entity_id == qr_record.id)
    )
    assert audit_evt is not None
    assert audit_evt.event_type == "QR_GENERATED"
    assert audit_evt.actor_user_id == processor.id
    assert audit_evt.metadata_json["packaging_lot_id"] == str(lot.id)
    assert "token" not in str(audit_evt.metadata_json)
    assert expected_hash not in str(audit_evt.metadata_json)


def test_create_qr_exactly_once(session: Session) -> None:
    """Duplicate QR generation on the same packaging lot must return 409 Conflict."""
    client = TestClient(app)
    processor = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-2@example.com", UserRole.PROCESSOR)
    beekeeper = _create_user(session, f"{TEST_EMAIL_PREFIX}bk-2@example.com", UserRole.BEEKEEPER)

    _, lot, _, _ = _setup_lineage_and_packaging(
        session, beekeeper, processor, f"{TEST_BATCH_PREFIX}002", f"{TEST_PACKAGE_LOT_PREFIX}002"
    )

    res1 = client.post(f"/packaging/{lot.id}/qr", headers=_auth_headers(processor))
    assert res1.status_code == 201

    res2 = client.post(f"/packaging/{lot.id}/qr", headers=_auth_headers(processor))
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"]


def test_create_qr_batch_prerequisites(session: Session) -> None:
    """Unfinalized, HOLD, or RECALL batch reject QR creation with 422."""
    client = TestClient(app)
    admin = _create_user(session, f"{TEST_EMAIL_PREFIX}adm-prereq@example.com", UserRole.ADMIN)
    processor = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-prereq@example.com", UserRole.PROCESSOR)
    beekeeper = _create_user(session, f"{TEST_EMAIL_PREFIX}bk-prereq@example.com", UserRole.BEEKEEPER)

    # 1. HOLD batch
    batch_hold, lot_hold, _, _ = _setup_lineage_and_packaging(
        session, beekeeper, processor, f"{TEST_BATCH_PREFIX}HLD", f"{TEST_PACKAGE_LOT_PREFIX}HLD"
    )
    # Update status to HOLD
    client.patch(
        f"/batches/{batch_hold.id}/status",
        headers=_auth_headers(admin),
        json={"status": "HOLD"},
    )
    res_hold = client.post(f"/packaging/{lot_hold.id}/qr", headers=_auth_headers(processor))
    assert res_hold.status_code == 422
    assert "HOLD" in res_hold.json()["detail"]

    # 2. RECALL batch
    batch_rcl, lot_rcl, _, _ = _setup_lineage_and_packaging(
        session, beekeeper, processor, f"{TEST_BATCH_PREFIX}RCL", f"{TEST_PACKAGE_LOT_PREFIX}RCL"
    )
    client.patch(
        f"/batches/{batch_rcl.id}/status",
        headers=_auth_headers(admin),
        json={"status": "RECALL"},
    )
    res_rcl = client.post(f"/packaging/{lot_rcl.id}/qr", headers=_auth_headers(processor))
    assert res_rcl.status_code == 422
    assert "RECALL" in res_rcl.json()["detail"]


def test_create_qr_rbac_and_ownership(session: Session) -> None:
    """Only ADMIN and owning PROCESSOR can generate QR. Other processor and beekeeper are rejected."""
    client = TestClient(app)
    processor1 = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-own1@example.com", UserRole.PROCESSOR)
    processor2 = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-own2@example.com", UserRole.PROCESSOR)
    beekeeper = _create_user(session, f"{TEST_EMAIL_PREFIX}bk-own@example.com", UserRole.BEEKEEPER)

    _, lot, _, _ = _setup_lineage_and_packaging(
        session, beekeeper, processor1, f"{TEST_BATCH_PREFIX}OWN", f"{TEST_PACKAGE_LOT_PREFIX}OWN"
    )

    # Beekeeper forbidden
    res_bk = client.post(f"/packaging/{lot.id}/qr", headers=_auth_headers(beekeeper))
    assert res_bk.status_code == 403

    # Other processor forbidden
    res_other = client.post(f"/packaging/{lot.id}/qr", headers=_auth_headers(processor2))
    assert res_other.status_code == 403

    # Unauthenticated forbidden (401)
    res_anon = client.post(f"/packaging/{lot.id}/qr")
    assert res_anon.status_code == 401


def test_create_qr_concurrency(session: Session) -> None:
    """Concurrent QR generation calls for the same packaging lot: exactly one 201, one 409."""
    client = TestClient(app)
    processor = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-conc@example.com", UserRole.PROCESSOR)
    beekeeper = _create_user(session, f"{TEST_EMAIL_PREFIX}bk-conc@example.com", UserRole.BEEKEEPER)

    _, lot, _, _ = _setup_lineage_and_packaging(
        session, beekeeper, processor, f"{TEST_BATCH_PREFIX}CNC", f"{TEST_PACKAGE_LOT_PREFIX}CNC"
    )

    def _call() -> int:
        c = TestClient(app)
        res = c.post(f"/packaging/{lot.id}/qr", headers=_auth_headers(processor))
        return res.status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(_call)
        f2 = executor.submit(_call)
        results = [f1.result(), f2.result()]

    assert sorted(results) == [201, 409]


# ===========================================================================
# 2. QR Metadata & Revocation
# ===========================================================================

def test_get_qr_metadata_rbac(session: Session) -> None:
    """Metadata access obeys batch read authorization."""
    client = TestClient(app)
    admin = _create_user(session, f"{TEST_EMAIL_PREFIX}adm-meta@example.com", UserRole.ADMIN)
    processor = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-meta@example.com", UserRole.PROCESSOR)
    other_proc = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-other-meta@example.com", UserRole.PROCESSOR)
    beekeeper = _create_user(session, f"{TEST_EMAIL_PREFIX}bk-meta@example.com", UserRole.BEEKEEPER)
    other_bk = _create_user(session, f"{TEST_EMAIL_PREFIX}bk-other-meta@example.com", UserRole.BEEKEEPER)

    _, lot, _, _ = _setup_lineage_and_packaging(
        session, beekeeper, processor, f"{TEST_BATCH_PREFIX}MET", f"{TEST_PACKAGE_LOT_PREFIX}MET"
    )

    # 404 before QR created
    res_pre = client.get(f"/packaging/{lot.id}/qr", headers=_auth_headers(processor))
    assert res_pre.status_code == 404

    # Create QR
    res_create = client.post(f"/packaging/{lot.id}/qr", headers=_auth_headers(processor))
    assert res_create.status_code == 201

    # ADMIN succeeds
    res_adm = client.get(f"/packaging/{lot.id}/qr", headers=_auth_headers(admin))
    assert res_adm.status_code == 200
    assert "token_hash" not in res_adm.json()

    # Owning PROCESSOR succeeds
    res_own = client.get(f"/packaging/{lot.id}/qr", headers=_auth_headers(processor))
    assert res_own.status_code == 200

    # Lineage BEEKEEPER succeeds
    res_lineage = client.get(f"/packaging/{lot.id}/qr", headers=_auth_headers(beekeeper))
    assert res_lineage.status_code == 200

    # Non-owning processor 403
    res_diff_proc = client.get(f"/packaging/{lot.id}/qr", headers=_auth_headers(other_proc))
    assert res_diff_proc.status_code == 403

    # Non-lineage beekeeper 403
    res_diff_bk = client.get(f"/packaging/{lot.id}/qr", headers=_auth_headers(other_bk))
    assert res_diff_bk.status_code == 403


def test_revoke_qr_admin_only_and_terminal(session: Session) -> None:
    """Only ADMIN can revoke QR; revocation is terminal (no second revocation, no reactivation)."""
    client = TestClient(app)
    admin = _create_user(session, f"{TEST_EMAIL_PREFIX}adm-rvk@example.com", UserRole.ADMIN)
    processor = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-rvk@example.com", UserRole.PROCESSOR)
    beekeeper = _create_user(session, f"{TEST_EMAIL_PREFIX}bk-rvk@example.com", UserRole.BEEKEEPER)

    _, lot, _, _ = _setup_lineage_and_packaging(
        session, beekeeper, processor, f"{TEST_BATCH_PREFIX}RVK", f"{TEST_PACKAGE_LOT_PREFIX}RVK"
    )
    res_create = client.post(f"/packaging/{lot.id}/qr", headers=_auth_headers(processor))
    qr_id = res_create.json()["id"]

    # Processor cannot revoke (403)
    res_proc_rvk = client.post(f"/qr/{qr_id}/revoke", headers=_auth_headers(processor))
    assert res_proc_rvk.status_code == 403

    # Beekeeper cannot revoke (403)
    res_bk_rvk = client.post(f"/qr/{qr_id}/revoke", headers=_auth_headers(beekeeper))
    assert res_bk_rvk.status_code == 403

    # Admin revokes successfully
    res_adm_rvk = client.post(f"/qr/{qr_id}/revoke", headers=_auth_headers(admin))
    assert res_adm_rvk.status_code == 200
    assert res_adm_rvk.json()["status"] == "REVOKED"

    # Terminal state check: second revocation returns 422
    res_repeat = client.post(f"/qr/{qr_id}/revoke", headers=_auth_headers(admin))
    assert res_repeat.status_code == 422
    assert "already revoked" in res_repeat.json()["detail"]

    # Check AuditEvent
    audit_evt = session.scalar(
        select(AuditEvent)
        .where(AuditEvent.entity_type == "QR_TOKEN")
        .where(AuditEvent.event_type == "QR_REVOKED")
    )
    assert audit_evt is not None
    assert audit_evt.actor_user_id == admin.id


# ===========================================================================
# 3. Public Consumer Verification & Edge Cases
# ===========================================================================

def test_consumer_verification_verified(session: Session) -> None:
    """Consumer verification endpoint is public and returns complete public-safe DTO."""
    client = TestClient(app)
    processor = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-cons@example.com", UserRole.PROCESSOR)
    beekeeper = _create_user(session, f"{TEST_EMAIL_PREFIX}bk-cons@example.com", UserRole.BEEKEEPER)

    batch, lot, harvest, _ = _setup_lineage_and_packaging(
        session, beekeeper, processor, f"{TEST_BATCH_PREFIX}CNS", f"{TEST_PACKAGE_LOT_PREFIX}CNS"
    )

    # Attach LabEvidence
    lab_record = LabEvidence(
        batch_id=batch.id,
        certificate_id=f"{TEST_CERT_PREFIX}001",
        test_summary="Purity test passed: 100% Raw Acacia Honey",
        file_name="cert_acacia_1.pdf",
        file_path="/var/internal/secrets/path/cert_acacia_1.pdf",
        file_hash_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        status=LabEvidenceStatus.ACTIVE,
        uploaded_at=datetime.now(UTC),
    )
    session.add(lab_record)

    # Attach BlockchainRecord
    bc_record = BlockchainRecord(
        batch_id=batch.id,
        event_type="BATCH_FINALIZED",
        transaction_hash="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        status=BlockchainStatus.CONFIRMED,
        network="hardhat-local",
        contract_address="0x5FbDB2315678afecb367f032d93F642f64180aa3",
        block_number=42,
        recorded_at=datetime.now(UTC),
    )
    session.add(bc_record)
    session.commit()

    # Create QR
    res_create = client.post(f"/packaging/{lot.id}/qr", headers=_auth_headers(processor))
    raw_token = res_create.json()["verification_url"].split("/verify/")[-1]

    # Consumer calls public GET /verify/{raw_token} WITHOUT any Authorization header
    res_verify = client.get(f"/verify/{raw_token}")
    assert res_verify.status_code == 200
    data = res_verify.json()

    assert data["verification_status"] == "VERIFIED"
    assert data["warning"] is None

    # Batch public info
    assert data["batch"]["batch_code"] == batch.batch_code
    assert data["batch"]["status"] == "ACTIVE"
    assert data["batch"]["is_finalized"] is True

    # Packaging public info
    assert data["packaging_lot"]["package_lot_code"] == lot.package_lot_code
    assert data["packaging_lot"]["quantity"] == lot.quantity
    assert data["packaging_lot"]["unit"] == "JARS"
    assert data["packaging_lot"]["package_size_grams"] == 500.0
    assert data["packaging_lot"]["packaged_quantity_kg"] == 50.0

    # Provenance
    assert len(data["provenance"]) >= 1
    prov = data["provenance"][0]
    assert prov["harvest_code"] == harvest.harvest_code
    assert "Black Forest" in prov["regions"]

    # Lab Evidence (verified public safe: NO file_path)
    assert len(data["lab_evidence"]) == 1
    lab = data["lab_evidence"][0]
    assert lab["certificate_id"] == f"{TEST_CERT_PREFIX}001"
    assert lab["test_summary"] == "Purity test passed: 100% Raw Acacia Honey"
    assert lab["file_name"] == "cert_acacia_1.pdf"
    assert "file_path" not in lab

    # Blockchain records
    assert len(data["blockchain_records"]) == 1
    bc = data["blockchain_records"][0]
    assert bc["transaction_hash"] == "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
    assert bc["block_number"] == 42


def test_consumer_verification_hold_and_recall_warnings(session: Session) -> None:
    """Batch under HOLD returns 200 with HOLD warning; under RECALL returns 200 with RECALL warning."""
    client = TestClient(app)
    admin = _create_user(session, f"{TEST_EMAIL_PREFIX}adm-warn@example.com", UserRole.ADMIN)
    processor = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-warn@example.com", UserRole.PROCESSOR)
    beekeeper = _create_user(session, f"{TEST_EMAIL_PREFIX}bk-warn@example.com", UserRole.BEEKEEPER)

    batch, lot, _, _ = _setup_lineage_and_packaging(
        session, beekeeper, processor, f"{TEST_BATCH_PREFIX}WRN", f"{TEST_PACKAGE_LOT_PREFIX}WRN"
    )
    res_create = client.post(f"/packaging/{lot.id}/qr", headers=_auth_headers(processor))
    raw_token = res_create.json()["verification_url"].split("/verify/")[-1]

    # 1. HOLD
    client.patch(
        f"/batches/{batch.id}/status",
        headers=_auth_headers(admin),
        json={"status": "HOLD"},
    )
    res_hold = client.get(f"/verify/{raw_token}")
    assert res_hold.status_code == 200
    data_hold = res_hold.json()
    assert data_hold["verification_status"] == "HOLD"
    assert data_hold["warning"] is not None
    assert "HOLD" in data_hold["warning"]

    # 2. RECALL (must transition HOLD -> ACTIVE -> RECALL)
    client.patch(
        f"/batches/{batch.id}/status",
        headers=_auth_headers(admin),
        json={"status": "ACTIVE"},
    )
    client.patch(
        f"/batches/{batch.id}/status",
        headers=_auth_headers(admin),
        json={"status": "RECALL"},
    )
    res_recall = client.get(f"/verify/{raw_token}")
    assert res_recall.status_code == 200
    data_recall = res_recall.json()
    assert data_recall["verification_status"] == "RECALLED"
    assert data_recall["warning"] is not None
    assert "RECALLED" in data_recall["warning"]


def test_consumer_verification_revoked_410(session: Session) -> None:
    """Revoked QR token returns 410 GONE."""
    client = TestClient(app)
    admin = _create_user(session, f"{TEST_EMAIL_PREFIX}adm-rev410@example.com", UserRole.ADMIN)
    processor = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-rev410@example.com", UserRole.PROCESSOR)
    beekeeper = _create_user(session, f"{TEST_EMAIL_PREFIX}bk-rev410@example.com", UserRole.BEEKEEPER)

    _, lot, _, _ = _setup_lineage_and_packaging(
        session, beekeeper, processor, f"{TEST_BATCH_PREFIX}410", f"{TEST_PACKAGE_LOT_PREFIX}410"
    )
    res_create = client.post(f"/packaging/{lot.id}/qr", headers=_auth_headers(processor))
    qr_id = res_create.json()["id"]
    raw_token = res_create.json()["verification_url"].split("/verify/")[-1]

    # Revoke QR
    client.post(f"/qr/{qr_id}/revoke", headers=_auth_headers(admin))

    # Consumer verification
    res_v = client.get(f"/verify/{raw_token}")
    assert res_v.status_code == 410
    assert "revoked" in res_v.json()["detail"].lower()


def test_consumer_verification_malformed_and_unknown_token(session: Session) -> None:
    """Malformed syntax or unknown tokens return 404 NOT FOUND."""
    client = TestClient(app)

    malformed_tokens = [
        "abc",
        "12345",
        "x" * 64,  # non-hex
        "a" * 63,  # wrong length
        "a" * 65,  # wrong length
        "' OR '1'='1",
        "../../etc/passwd",
    ]
    for token in malformed_tokens:
        res = client.get(f"/verify/{token}")
        assert res.status_code == 404, f"Failed for token {token}: {res.status_code}"

    # Unknown 64-hex token
    unknown_token = "0" * 64
    res_unknown = client.get(f"/verify/{unknown_token}")
    assert res_unknown.status_code == 404


def test_consumer_verification_confidentiality_dto_safety(session: Session) -> None:
    """Validate that consumer endpoint does not leak any internal IDs, GPS, or secrets."""
    client = TestClient(app)
    processor = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-safe@example.com", UserRole.PROCESSOR)
    beekeeper = _create_user(session, f"{TEST_EMAIL_PREFIX}bk-safe@example.com", UserRole.BEEKEEPER)

    batch, lot, harvest, hive = _setup_lineage_and_packaging(
        session, beekeeper, processor, f"{TEST_BATCH_PREFIX}SFE", f"{TEST_PACKAGE_LOT_PREFIX}SFE"
    )
    res_create = client.post(f"/packaging/{lot.id}/qr", headers=_auth_headers(processor))
    raw_token = res_create.json()["verification_url"].split("/verify/")[-1]

    res_verify = client.get(f"/verify/{raw_token}")
    assert res_verify.status_code == 200
    body = res_verify.text

    # Forbidden internal data checks
    forbidden_strings = [
        str(processor.id),
        str(beekeeper.id),
        str(batch.id),
        str(lot.id),
        str(harvest.id),
        str(hive.id),
        "token_hash",
        "password",
        "/var/",
        "/tmp/",
    ]
    for secret in forbidden_strings:
        assert secret not in body, f"Data leak: '{secret}' found in consumer response"


def test_create_qr_unfinalized_batch(session: Session) -> None:
    """Packaging lot under unfinalized batch cannot have QR generated."""
    client = TestClient(app)
    processor = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-unfin@example.com", UserRole.PROCESSOR)
    beekeeper = _create_user(session, f"{TEST_EMAIL_PREFIX}bk-unfin@example.com", UserRole.BEEKEEPER)

    # Lineage with finalize_batch=False
    unique_suffix = uuid4().hex[:6]
    hive = _create_hive(session, f"{TEST_HIVE_PREFIX}{unique_suffix}", beekeeper)

    # Harvest
    res_h = client.post(
        "/harvests",
        headers=_auth_headers(beekeeper),
        json={
            "harvest_code": f"{TEST_HARVEST_PREFIX}{unique_suffix}",
            "harvest_date": str(date.today()),
            "quantity_kg": 50.0,
        },
    )
    harvest_id = res_h.json()["id"]
    client.post(
        f"/harvests/{harvest_id}/hives",
        headers=_auth_headers(beekeeper),
        json={"hive_id": str(hive.id), "quantity_used_kg": 50.0},
    )
    client.post(f"/harvests/{harvest_id}/finalize", headers=_auth_headers(beekeeper))

    # Collection Lot
    res_lot = client.post(
        "/collection-lots",
        headers=_auth_headers(processor),
        json={"lot_code": f"{TEST_LOT_PREFIX}{unique_suffix}", "quantity_kg": 50.0},
    )
    lot_id = res_lot.json()["id"]
    client.post(
        f"/collection-lots/{lot_id}/harvests",
        headers=_auth_headers(processor),
        json={"harvest_id": harvest_id, "quantity_used_kg": 50.0},
    )
    client.post(f"/collection-lots/{lot_id}/finalize", headers=_auth_headers(processor))

    # Batch (UNFINALIZED)
    res_b = client.post(
        "/batches",
        headers=_auth_headers(processor),
        json={"batch_code": f"{TEST_BATCH_PREFIX}UNF"},
    )
    batch_id = res_b.json()["id"]
    client.post(
        f"/batches/{batch_id}/collection-lots",
        headers=_auth_headers(processor),
        json={"collection_lot_id": lot_id, "quantity_used_kg": 50.0},
    )

    # Direct DB insertion of packaging lot under unfinalized batch
    pkg = PackagingLot(
        package_lot_code=f"{TEST_PACKAGE_LOT_PREFIX}UNF",
        batch_id=UUID(batch_id),
        quantity=10,
        unit=PackagingUnit.JARS,
        package_size_grams=Decimal("500.00"),
    )
    session.add(pkg)
    session.commit()

    res = client.post(f"/packaging/{pkg.id}/qr", headers=_auth_headers(processor))
    assert res.status_code == 422
    assert "unfinalized" in res.json()["detail"].lower()


def test_consumer_verification_unfinalized_batch_404(session: Session) -> None:
    """Consumer verification returns 404 if batch is somehow unfinalized."""
    client = TestClient(app)
    processor = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-unf-v@example.com", UserRole.PROCESSOR)
    beekeeper = _create_user(session, f"{TEST_EMAIL_PREFIX}bk-unf-v@example.com", UserRole.BEEKEEPER)

    batch, lot, _, _ = _setup_lineage_and_packaging(
        session, beekeeper, processor, f"{TEST_BATCH_PREFIX}UNFV", f"{TEST_PACKAGE_LOT_PREFIX}UNFV"
    )
    res_create = client.post(f"/packaging/{lot.id}/qr", headers=_auth_headers(processor))
    raw_token = res_create.json()["verification_url"].split("/verify/")[-1]

    # Unfinalize batch directly in database (finalized_at must be None to satisfy ck constraint)
    batch.is_finalized = False
    batch.finalized_at = None
    session.commit()

    res_verify = client.get(f"/verify/{raw_token}")
    assert res_verify.status_code == 404


def test_qr_collision_handling(monkeypatch: pytest.MonkeyPatch, session: Session) -> None:
    """If generated token hash collides with an existing one, IntegrityError maps to 409."""
    import secrets

    client = TestClient(app)
    processor = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-col@example.com", UserRole.PROCESSOR)
    beekeeper = _create_user(session, f"{TEST_EMAIL_PREFIX}bk-col@example.com", UserRole.BEEKEEPER)

    _, lot1, _, _ = _setup_lineage_and_packaging(
        session, beekeeper, processor, f"{TEST_BATCH_PREFIX}CL1", f"{TEST_PACKAGE_LOT_PREFIX}CL1"
    )
    _, lot2, _, _ = _setup_lineage_and_packaging(
        session, beekeeper, processor, f"{TEST_BATCH_PREFIX}CL2", f"{TEST_PACKAGE_LOT_PREFIX}CL2"
    )

    # First generation succeeds with a fixed token
    fixed_token = "a" * 64
    monkeypatch.setattr(secrets, "token_hex", lambda n: fixed_token)
    res1 = client.post(f"/packaging/{lot1.id}/qr", headers=_auth_headers(processor))
    assert res1.status_code == 201

    # Second generation collides on token_hash
    res2 = client.post(f"/packaging/{lot2.id}/qr", headers=_auth_headers(processor))
    assert res2.status_code == 409


def test_no_blockchain_link_packaging_invoked() -> None:
    """Verify statically that linkPackaging is never imported or called in the qr module."""
    from pathlib import Path

    qr_dir = Path(__file__).resolve().parent.parent / "app" / "qr"
    for py_file in qr_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert "linkPackaging" not in content
        assert "link_packaging" not in content
