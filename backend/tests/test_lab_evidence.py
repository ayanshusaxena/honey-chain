"""Comprehensive test suite for Honey Chain Lab Evidence and SHA-256 slice."""

from __future__ import annotations

import hashlib
import io
from collections.abc import Generator
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth.security import create_access_token, hash_password
from app.core.database import SessionLocal
from app.lab.service import STORAGE_DIR
from app.main import app
from app.models.audit import AuditEvent
from app.models.enums import BatchStatus, HiveStatus, LabEvidenceStatus, UserRole
from app.models.evidence import LabEvidence
from app.models.hive import Harvest, Hive, HiveHarvest
from app.models.identity import User
from app.models.traceability import Batch, BatchCollectionLot, CollectionLot, CollectionLotHarvest

TEST_EMAIL_PREFIX = "test-lab-"
TEST_HIVE_PREFIX = "LAB-HIV-"
TEST_HARVEST_PREFIX = "LAB-HRV-"
TEST_LOT_PREFIX = "LAB-LOT-"
TEST_BATCH_PREFIX = "LAB-BAT-"
TEST_CERT_PREFIX = "LAB-CERT-"

_created_test_files: list[Path] = []


def _cleanup(database_session: Session) -> None:
    # Clean up physical files created during test
    global _created_test_files
    for file_path in _created_test_files:
        if file_path.exists():
            try:
                file_path.unlink()
            except OSError:
                pass
    _created_test_files = []

    # Clean up database records
    database_session.execute(delete(LabEvidence).where(LabEvidence.certificate_id.like(f"{TEST_CERT_PREFIX}%")))
    database_session.execute(delete(AuditEvent).where(AuditEvent.entity_type == "LAB_EVIDENCE"))
    database_session.execute(delete(BatchCollectionLot))
    database_session.execute(delete(CollectionLotHarvest))
    database_session.execute(delete(HiveHarvest))
    database_session.execute(delete(Batch).where(Batch.batch_code.like(f"{TEST_BATCH_PREFIX}%")))
    database_session.execute(delete(CollectionLot).where(CollectionLot.lot_code.like(f"{TEST_LOT_PREFIX}%")))
    database_session.execute(delete(Harvest).where(Harvest.harvest_code.like(f"{TEST_HARVEST_PREFIX}%")))
    database_session.execute(delete(Hive).where(Hive.hive_code.like(f"{TEST_HIVE_PREFIX}%")))
    database_session.execute(delete(User).where(User.email.like(f"{TEST_EMAIL_PREFIX}%")))
    database_session.commit()


@pytest.fixture
def session() -> Generator[Session, None, None]:
    if SessionLocal is None:
        pytest.skip("HONEY_CHAIN_DATABASE_URL is not configured.")

    with SessionLocal() as database_session:
        _cleanup(database_session)
        try:
            yield database_session
        finally:
            _cleanup(database_session)


# ===========================================================================
# Helper Factories
# ===========================================================================

def _create_user(
    session: Session,
    *,
    email: str,
    role: UserRole,
    name: str | None = None,
    is_active: bool = True,
) -> User:
    user = User(
        name=name or f"Test {role.value}",
        email=email.lower(),
        password_hash=hash_password("secure-test-pass"),
        role=role,
        is_active=is_active,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def _create_batch(
    session: Session,
    *,
    batch_code: str,
    processor: User,
    status: BatchStatus = BatchStatus.ACTIVE,
    is_finalized: bool = False,
) -> Batch:
    batch = Batch(
        batch_code=batch_code,
        processor_id=processor.id,
        status=status,
        is_finalized=is_finalized,
        finalized_at=datetime.now(UTC) if is_finalized else None,
    )
    session.add(batch)
    session.commit()
    session.refresh(batch)
    return batch


def _track_file(file_path_str: str) -> None:
    p = Path(file_path_str)
    if not p.is_absolute():
        repo_root = Path(__file__).resolve().parents[2]
        p = repo_root / file_path_str
    _created_test_files.append(p)


# ===========================================================================
# 1. Unauthenticated Requests
# ===========================================================================

def test_unauthenticated_requests_are_rejected() -> None:
    client = TestClient(app)
    fake_id = uuid4()

    assert client.post(f"/batches/{fake_id}/lab-evidence", data={}).status_code == 401
    assert client.get(f"/batches/{fake_id}/lab-evidence").status_code == 401
    assert client.get(f"/lab-evidence/{fake_id}").status_code == 401
    assert client.get(f"/lab-evidence/{fake_id}/download").status_code == 401
    assert client.get(f"/lab-evidence/{fake_id}/verify").status_code == 401


# ===========================================================================
# 2. Upload Lifecycle and Correctness
# ===========================================================================

def test_processor_can_upload_pdf_evidence_to_own_batch(session: Session) -> None:
    client = TestClient(app)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}proc1@example.com", role=UserRole.PROCESSOR)
    batch = _create_batch(session, batch_code=f"{TEST_BATCH_PREFIX}001", processor=processor)

    cert_id = f"{TEST_CERT_PREFIX}001"
    pdf_content = b"%PDF-1.4 sample lab report content for verification"
    expected_sha256 = hashlib.sha256(pdf_content).hexdigest().lower()

    response = client.post(
        f"/batches/{batch.id}/lab-evidence",
        headers=_auth_headers(processor),
        data={
            "certificate_id": cert_id,
            "test_summary": "Purity and pollen analysis passed demo thresholds.",
        },
        files={
            "file": ("lab_report.pdf", io.BytesIO(pdf_content), "application/pdf"),
        },
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["batch_id"] == str(batch.id)
    assert data["certificate_id"] == cert_id
    assert data["test_summary"] == "Purity and pollen analysis passed demo thresholds."
    assert data["file_name"] == "lab_report.pdf"
    assert data["file_hash_sha256"] == expected_sha256
    assert data["status"] == "ACTIVE"
    assert "uploaded_at" in data
    # Ensure internal file path is not leaked in response
    assert "file_path" not in data

    # Verify DB persistence
    evidence_id = UUID(data["id"])
    db_evidence = session.scalar(select(LabEvidence).where(LabEvidence.id == evidence_id))
    assert db_evidence is not None
    assert db_evidence.file_hash_sha256 == expected_sha256
    assert db_evidence.status == LabEvidenceStatus.ACTIVE
    _track_file(db_evidence.file_path)

    # Verify AuditEvent was created
    audit = session.scalar(
        select(AuditEvent).where(
            AuditEvent.event_type == "LAB_EVIDENCE_UPLOADED",
            AuditEvent.entity_id == evidence_id,
        )
    )
    assert audit is not None
    assert audit.actor_user_id == processor.id
    assert audit.metadata_json["file_hash_sha256"] == expected_sha256
    assert audit.metadata_json["certificate_id"] == cert_id


def test_admin_can_upload_evidence_to_any_batch(session: Session) -> None:
    client = TestClient(app)
    admin = _create_user(session, email=f"{TEST_EMAIL_PREFIX}admin@example.com", role=UserRole.ADMIN)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}proc2@example.com", role=UserRole.PROCESSOR)
    batch = _create_batch(session, batch_code=f"{TEST_BATCH_PREFIX}002", processor=processor)

    cert_id = f"{TEST_CERT_PREFIX}002"
    pdf_content = b"%PDF-1.4 admin upload test"

    response = client.post(
        f"/batches/{batch.id}/lab-evidence",
        headers=_auth_headers(admin),
        data={
            "certificate_id": cert_id,
            "test_summary": "Admin uploaded lab certificate.",
        },
        files={
            "file": ("admin_report.pdf", io.BytesIO(pdf_content), "application/pdf"),
        },
    )

    assert response.status_code == 201, response.text
    evidence_id = UUID(response.json()["id"])
    db_evidence = session.scalar(select(LabEvidence).where(LabEvidence.id == evidence_id))
    assert db_evidence is not None
    _track_file(db_evidence.file_path)


# ===========================================================================
# 3. Authorization Boundaries
# ===========================================================================

def test_processor_cannot_upload_evidence_to_another_processors_batch(session: Session) -> None:
    client = TestClient(app)
    processor1 = _create_user(session, email=f"{TEST_EMAIL_PREFIX}proc_owner@example.com", role=UserRole.PROCESSOR)
    processor2 = _create_user(session, email=f"{TEST_EMAIL_PREFIX}proc_other@example.com", role=UserRole.PROCESSOR)
    batch = _create_batch(session, batch_code=f"{TEST_BATCH_PREFIX}003", processor=processor1)

    response = client.post(
        f"/batches/{batch.id}/lab-evidence",
        headers=_auth_headers(processor2),
        data={
            "certificate_id": f"{TEST_CERT_PREFIX}cross",
            "test_summary": "Should be forbidden",
        },
        files={
            "file": ("cross.pdf", io.BytesIO(b"%PDF-1.4 cross"), "application/pdf"),
        },
    )

    assert response.status_code == 403
    assert "only upload lab evidence for their own batches" in response.json()["detail"].lower()


def test_beekeeper_cannot_upload_evidence(session: Session) -> None:
    client = TestClient(app)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}proc_bk@example.com", role=UserRole.PROCESSOR)
    beekeeper = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk_uploader@example.com", role=UserRole.BEEKEEPER)
    batch = _create_batch(session, batch_code=f"{TEST_BATCH_PREFIX}004", processor=processor)

    response = client.post(
        f"/batches/{batch.id}/lab-evidence",
        headers=_auth_headers(beekeeper),
        data={
            "certificate_id": f"{TEST_CERT_PREFIX}bk_cert",
            "test_summary": "Beekeeper upload attempt",
        },
        files={
            "file": ("bk.pdf", io.BytesIO(b"%PDF-1.4 bk"), "application/pdf"),
        },
    )

    assert response.status_code == 403
    assert "beekeepers cannot upload" in response.json()["detail"].lower()


# ===========================================================================
# 4. File Validation and SHA-256 Hashing Rules
# ===========================================================================

def test_sha256_hash_calculation_is_exact_deterministic_and_lowercase(session: Session) -> None:
    client = TestClient(app)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}sha_proc@example.com", role=UserRole.PROCESSOR)
    batch = _create_batch(session, batch_code=f"{TEST_BATCH_PREFIX}sha", processor=processor)

    # Known arbitrary payload
    test_bytes = b"%PDF-1.5 \x00\x01\x02 Test PDF payload for hash consistency \xff"
    expected_hex = hashlib.sha256(test_bytes).hexdigest().lower()

    response = client.post(
        f"/batches/{batch.id}/lab-evidence",
        headers=_auth_headers(processor),
        data={
            "certificate_id": f"{TEST_CERT_PREFIX}sha",
            "test_summary": "SHA verification",
        },
        files={
            "file": ("cert.pdf", io.BytesIO(test_bytes), "application/pdf"),
        },
    )

    assert response.status_code == 201
    assert response.json()["file_hash_sha256"] == expected_hex
    db_ev = session.scalar(select(LabEvidence).where(LabEvidence.certificate_id == f"{TEST_CERT_PREFIX}sha"))
    if db_ev:
        _track_file(db_ev.file_path)


def test_non_pdf_upload_is_rejected(session: Session) -> None:
    client = TestClient(app)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}non_pdf@example.com", role=UserRole.PROCESSOR)
    batch = _create_batch(session, batch_code=f"{TEST_BATCH_PREFIX}non_pdf", processor=processor)

    # 1. Non-pdf extension rejected
    r1 = client.post(
        f"/batches/{batch.id}/lab-evidence",
        headers=_auth_headers(processor),
        data={
            "certificate_id": f"{TEST_CERT_PREFIX}txt",
            "test_summary": "Invalid text file",
        },
        files={
            "file": ("report.txt", io.BytesIO(b"Plain text content"), "text/plain"),
        },
    )
    assert r1.status_code == 400
    assert "only pdf" in r1.json()["detail"].lower()

    # 2. .pdf extension but missing %PDF- signature rejected
    r2 = client.post(
        f"/batches/{batch.id}/lab-evidence",
        headers=_auth_headers(processor),
        data={
            "certificate_id": f"{TEST_CERT_PREFIX}fake_pdf",
            "test_summary": "Fake PDF file without signature",
        },
        files={
            "file": ("fake.pdf", io.BytesIO(b"NOT A REAL PDF HEADER"), "application/pdf"),
        },
    )
    assert r2.status_code == 400
    assert "%pdf-" in r2.json()["detail"].lower()


def test_empty_file_upload_is_rejected(session: Session) -> None:
    client = TestClient(app)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}empty@example.com", role=UserRole.PROCESSOR)
    batch = _create_batch(session, batch_code=f"{TEST_BATCH_PREFIX}empty", processor=processor)

    response = client.post(
        f"/batches/{batch.id}/lab-evidence",
        headers=_auth_headers(processor),
        data={
            "certificate_id": f"{TEST_CERT_PREFIX}empty",
            "test_summary": "Empty report",
        },
        files={
            "file": ("empty.pdf", io.BytesIO(b""), "application/pdf"),
        },
    )

    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_file_exceeding_10mb_is_rejected(session: Session) -> None:
    client = TestClient(app)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}oversize@example.com", role=UserRole.PROCESSOR)
    batch = _create_batch(session, batch_code=f"{TEST_BATCH_PREFIX}oversize", processor=processor)

    # Valid %PDF- signature but exceeds 10 MB limit
    oversized_bytes = b"%PDF-1.4 " + b"0" * (10 * 1024 * 1024 + 1)

    response = client.post(
        f"/batches/{batch.id}/lab-evidence",
        headers=_auth_headers(processor),
        data={
            "certificate_id": f"{TEST_CERT_PREFIX}oversize",
            "test_summary": "Oversized report",
        },
        files={
            "file": ("large.pdf", io.BytesIO(oversized_bytes), "application/pdf"),
        },
    )

    assert response.status_code == 400
    assert "10 mb" in response.json()["detail"].lower()


def test_duplicate_certificate_id_is_rejected(session: Session) -> None:
    client = TestClient(app)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}dup@example.com", role=UserRole.PROCESSOR)
    batch = _create_batch(session, batch_code=f"{TEST_BATCH_PREFIX}dup", processor=processor)

    cert_id = f"{TEST_CERT_PREFIX}duplicate"

    # First upload succeeds
    r1 = client.post(
        f"/batches/{batch.id}/lab-evidence",
        headers=_auth_headers(processor),
        data={"certificate_id": cert_id, "test_summary": "First"},
        files={"file": ("c1.pdf", io.BytesIO(b"%PDF-1.4 first"), "application/pdf")},
    )
    assert r1.status_code == 201
    db_ev = session.scalar(select(LabEvidence).where(LabEvidence.certificate_id == cert_id))
    if db_ev:
        _track_file(db_ev.file_path)

    # Second upload with same certificate_id fails with 409
    r2 = client.post(
        f"/batches/{batch.id}/lab-evidence",
        headers=_auth_headers(processor),
        data={"certificate_id": cert_id, "test_summary": "Second"},
        files={"file": ("c2.pdf", io.BytesIO(b"%PDF-1.4 second"), "application/pdf")},
    )
    assert r2.status_code == 409
    assert "already exists" in r2.json()["detail"].lower()


def test_duplicate_certificate_race_integrity_error_handled(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    client = TestClient(app)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}race@example.com", role=UserRole.PROCESSOR)
    batch = _create_batch(session, batch_code=f"{TEST_BATCH_PREFIX}race", processor=processor)

    from sqlalchemy.exc import IntegrityError

    # Simulate concurrent race where pre-check passed but session.commit raises IntegrityError
    def mock_commit(self: Session) -> None:
        raise IntegrityError("duplicate key value violates unique constraint uq_lab_evidence_certificate_id", params={}, orig=Exception())

    monkeypatch.setattr(Session, "commit", mock_commit)

    response = client.post(
        f"/batches/{batch.id}/lab-evidence",
        headers=_auth_headers(processor),
        data={
            "certificate_id": f"{TEST_CERT_PREFIX}race_cert",
            "test_summary": "Simulated race condition",
        },
        files={
            "file": ("race.pdf", io.BytesIO(b"%PDF-1.4 race test"), "application/pdf"),
        },
    )

    assert response.status_code == 409
    assert "certificate id already exists" in response.json()["detail"].lower()


def test_upload_to_nonexistent_batch_returns_404(session: Session) -> None:
    client = TestClient(app)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}nobatch@example.com", role=UserRole.PROCESSOR)
    fake_batch_id = uuid4()

    response = client.post(
        f"/batches/{fake_batch_id}/lab-evidence",
        headers=_auth_headers(processor),
        data={
            "certificate_id": f"{TEST_CERT_PREFIX}nobatch",
            "test_summary": "Nonexistent batch",
        },
        files={
            "file": ("nobatch.pdf", io.BytesIO(b"%PDF-1.4 test"), "application/pdf"),
        },
    )

    assert response.status_code == 404
    assert "batch not found" in response.json()["detail"].lower()


# ===========================================================================
# 5. Batch Status and Finalization Interactions (Rules 16 & 17)
# ===========================================================================

def test_evidence_allowed_for_unfinalized_and_finalized_active_batches(session: Session) -> None:
    client = TestClient(app)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}fin_proc@example.com", role=UserRole.PROCESSOR)

    # 1. Unfinalized ACTIVE batch
    batch_unfinalized = _create_batch(
        session, batch_code=f"{TEST_BATCH_PREFIX}unfin", processor=processor, is_finalized=False
    )
    r1 = client.post(
        f"/batches/{batch_unfinalized.id}/lab-evidence",
        headers=_auth_headers(processor),
        data={
            "certificate_id": f"{TEST_CERT_PREFIX}unfin",
            "test_summary": "Evidence on unfinalized batch",
        },
        files={"file": ("unfin.pdf", io.BytesIO(b"%PDF-1.4 unfin"), "application/pdf")},
    )
    assert r1.status_code == 201
    db_ev1 = session.scalar(select(LabEvidence).where(LabEvidence.certificate_id == f"{TEST_CERT_PREFIX}unfin"))
    if db_ev1:
        _track_file(db_ev1.file_path)

    # 2. Finalized ACTIVE batch
    batch_finalized = _create_batch(
        session, batch_code=f"{TEST_BATCH_PREFIX}fin", processor=processor, is_finalized=True
    )
    r2 = client.post(
        f"/batches/{batch_finalized.id}/lab-evidence",
        headers=_auth_headers(processor),
        data={
            "certificate_id": f"{TEST_CERT_PREFIX}fin",
            "test_summary": "Evidence on finalized batch",
        },
        files={"file": ("fin.pdf", io.BytesIO(b"%PDF-1.4 fin"), "application/pdf")},
    )
    assert r2.status_code == 201
    db_ev2 = session.scalar(select(LabEvidence).where(LabEvidence.certificate_id == f"{TEST_CERT_PREFIX}fin"))
    if db_ev2:
        _track_file(db_ev2.file_path)


def test_evidence_creation_allowed_for_hold_and_recall_batches(session: Session) -> None:
    client = TestClient(app)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}status_proc@example.com", role=UserRole.PROCESSOR)

    # Batch on HOLD
    batch_hold = _create_batch(
        session, batch_code=f"{TEST_BATCH_PREFIX}hold", processor=processor, status=BatchStatus.HOLD
    )
    r_hold = client.post(
        f"/batches/{batch_hold.id}/lab-evidence",
        headers=_auth_headers(processor),
        data={
            "certificate_id": f"{TEST_CERT_PREFIX}hold",
            "test_summary": "Evidence uploaded while batch is on HOLD",
        },
        files={"file": ("hold.pdf", io.BytesIO(b"%PDF-1.4 hold"), "application/pdf")},
    )
    assert r_hold.status_code == 201
    db_ev_hold = session.scalar(select(LabEvidence).where(LabEvidence.certificate_id == f"{TEST_CERT_PREFIX}hold"))
    if db_ev_hold:
        _track_file(db_ev_hold.file_path)

    # Batch on RECALL
    batch_recall = _create_batch(
        session, batch_code=f"{TEST_BATCH_PREFIX}recall", processor=processor, status=BatchStatus.RECALL
    )
    r_recall = client.post(
        f"/batches/{batch_recall.id}/lab-evidence",
        headers=_auth_headers(processor),
        data={
            "certificate_id": f"{TEST_CERT_PREFIX}recall",
            "test_summary": "Evidence uploaded while batch is on RECALL",
        },
        files={"file": ("recall.pdf", io.BytesIO(b"%PDF-1.4 recall"), "application/pdf")},
    )
    assert r_recall.status_code == 201
    db_ev_recall = session.scalar(select(LabEvidence).where(LabEvidence.certificate_id == f"{TEST_CERT_PREFIX}recall"))
    if db_ev_recall:
        _track_file(db_ev_recall.file_path)


# ===========================================================================
# 6. Read, Download, and Verify Endpoints
# ===========================================================================

def test_read_and_download_evidence_endpoints(session: Session) -> None:
    client = TestClient(app)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}read_proc@example.com", role=UserRole.PROCESSOR)
    batch = _create_batch(session, batch_code=f"{TEST_BATCH_PREFIX}read", processor=processor)

    pdf_bytes = b"%PDF-1.4 downloaded certificate content"
    cert_id = f"{TEST_CERT_PREFIX}read"

    create_resp = client.post(
        f"/batches/{batch.id}/lab-evidence",
        headers=_auth_headers(processor),
        data={"certificate_id": cert_id, "test_summary": "Testing read endpoints"},
        files={"file": ("original_cert.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert create_resp.status_code == 201
    evidence_id = create_resp.json()["id"]

    # 1. GET /batches/{batch_id}/lab-evidence
    list_resp = client.get(f"/batches/{batch.id}/lab-evidence", headers=_auth_headers(processor))
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 1
    assert items[0]["id"] == evidence_id
    assert "file_path" not in items[0]

    # 2. GET /lab-evidence/{evidence_id}
    detail_resp = client.get(f"/lab-evidence/{evidence_id}", headers=_auth_headers(processor))
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == evidence_id
    assert "file_path" not in detail_resp.json()

    # 3. GET /lab-evidence/{evidence_id}/download
    download_resp = client.get(f"/lab-evidence/{evidence_id}/download", headers=_auth_headers(processor))
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"] == "application/pdf"
    assert download_resp.content == pdf_bytes

    db_ev = session.scalar(select(LabEvidence).where(LabEvidence.id == UUID(evidence_id)))
    if db_ev:
        _track_file(db_ev.file_path)


def test_verify_lab_evidence_hash_endpoint(session: Session) -> None:
    """Verify endpoint computes SHA-256 over physical file and returns claim boundary."""
    client = TestClient(app)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}vfy_proc@example.com", role=UserRole.PROCESSOR)
    batch = _create_batch(session, batch_code=f"{TEST_BATCH_PREFIX}vfy", processor=processor)

    pdf_bytes = b"%PDF-1.4 verifiable lab report content"
    expected_hash = hashlib.sha256(pdf_bytes).hexdigest().lower()
    cert_id = f"{TEST_CERT_PREFIX}vfy"

    create_resp = client.post(
        f"/batches/{batch.id}/lab-evidence",
        headers=_auth_headers(processor),
        data={"certificate_id": cert_id, "test_summary": "Verification test"},
        files={"file": ("vfy_cert.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert create_resp.status_code == 201
    evidence_id = create_resp.json()["id"]

    # Call GET /lab-evidence/{evidence_id}/verify
    verify_resp = client.get(f"/lab-evidence/{evidence_id}/verify", headers=_auth_headers(processor))
    assert verify_resp.status_code == 200
    vdata = verify_resp.json()
    assert vdata["evidence_id"] == evidence_id
    assert vdata["batch_id"] == str(batch.id)
    assert vdata["certificate_id"] == cert_id
    assert vdata["file_hash_sha256"] == expected_hash
    assert vdata["computed_hash_sha256"] == expected_hash
    assert vdata["is_hash_verified"] is True
    assert vdata["is_verified"] is True
    assert "file_path" not in vdata

    # Verify claim boundary statement
    expected_claim = "The evidence artifact was recorded and its hash is verifiable."
    assert vdata["claim"] == expected_claim
    assert vdata["claim_statement"] == expected_claim

    db_ev = session.scalar(select(LabEvidence).where(LabEvidence.id == UUID(evidence_id)))
    if db_ev:
        _track_file(db_ev.file_path)


def test_verify_lab_evidence_detects_file_tampering(session: Session) -> None:
    """If file on disk is tampered, verify endpoint detects mismatch (is_hash_verified=False)."""
    client = TestClient(app)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}tamp_proc@example.com", role=UserRole.PROCESSOR)
    batch = _create_batch(session, batch_code=f"{TEST_BATCH_PREFIX}tamp", processor=processor)

    pdf_bytes = b"%PDF-1.4 original certificate content"
    cert_id = f"{TEST_CERT_PREFIX}tamp"

    create_resp = client.post(
        f"/batches/{batch.id}/lab-evidence",
        headers=_auth_headers(processor),
        data={"certificate_id": cert_id, "test_summary": "Tamper test"},
        files={"file": ("tamp_cert.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert create_resp.status_code == 201
    evidence_id = create_resp.json()["id"]

    db_ev = session.scalar(select(LabEvidence).where(LabEvidence.id == UUID(evidence_id)))
    assert db_ev is not None
    _track_file(db_ev.file_path)

    # Tamper with file on disk directly
    file_path = Path(db_ev.file_path)
    if not file_path.is_absolute():
        repo_root = Path(__file__).resolve().parents[2]
        file_path = repo_root / db_ev.file_path
    file_path.write_bytes(b"%PDF-1.4 TAMPERED CONTENT WITH MALICIOUS ALTERATIONS")

    # Verify returns mismatch
    verify_resp = client.get(f"/lab-evidence/{evidence_id}/verify", headers=_auth_headers(processor))
    assert verify_resp.status_code == 200
    vdata = verify_resp.json()
    assert vdata["is_hash_verified"] is False
    assert vdata["is_verified"] is False
    assert vdata["computed_hash_sha256"] != vdata["file_hash_sha256"]


def test_multiple_lab_evidence_per_batch(session: Session) -> None:
    """A batch can have multiple lab evidence records."""
    client = TestClient(app)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}multi_proc@example.com", role=UserRole.PROCESSOR)
    batch = _create_batch(session, batch_code=f"{TEST_BATCH_PREFIX}multi", processor=processor)

    # Upload 3 evidence files
    for i in range(1, 4):
        resp = client.post(
            f"/batches/{batch.id}/lab-evidence",
            headers=_auth_headers(processor),
            data={
                "certificate_id": f"{TEST_CERT_PREFIX}multi_{i}",
                "test_summary": f"Test report {i}",
            },
            files={"file": (f"report_{i}.pdf", io.BytesIO(f"%PDF-1.4 report {i}".encode()), "application/pdf")},
        )
        assert resp.status_code == 201
        evidence_id = resp.json()["id"]
        db_ev = session.scalar(select(LabEvidence).where(LabEvidence.id == UUID(evidence_id)))
        if db_ev:
            _track_file(db_ev.file_path)

    # List all evidence for batch
    list_resp = client.get(f"/batches/{batch.id}/lab-evidence", headers=_auth_headers(processor))
    assert list_resp.status_code == 200
    records = list_resp.json()
    assert len(records) == 3


# ===========================================================================
# 7. Lineage Access Control for Beekeepers
# ===========================================================================

def test_beekeeper_can_read_evidence_only_for_batches_with_own_lineage(session: Session) -> None:
    client = TestClient(app)
    admin = _create_user(session, email=f"{TEST_EMAIL_PREFIX}admin_lineage@example.com", role=UserRole.ADMIN)
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}proc_lineage@example.com", role=UserRole.PROCESSOR)
    bk1 = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk1_lineage@example.com", role=UserRole.BEEKEEPER)
    bk2 = _create_user(session, email=f"{TEST_EMAIL_PREFIX}bk2_no_lineage@example.com", role=UserRole.BEEKEEPER)

    # Setup lineage: bk1 owns a harvest included in collection_lot included in batch
    hive1 = Hive(
        hive_code=f"{TEST_HIVE_PREFIX}01",
        beekeeper_id=bk1.id,
        location_region="Valley",
        status=HiveStatus.ACTIVE,
    )
    session.add(hive1)
    session.commit()

    harvest1 = Harvest(
        harvest_code=f"{TEST_HARVEST_PREFIX}01",
        quantity_kg=50.0,
        harvest_date=date.today(),
        created_by_id=bk1.id,
        is_finalized=True,
        finalized_at=datetime.now(UTC),
    )
    session.add(harvest1)
    session.commit()

    hh = HiveHarvest(hive_id=hive1.id, harvest_id=harvest1.id, quantity_used_kg=50.0)
    session.add(hh)

    lot = CollectionLot(
        lot_code=f"{TEST_LOT_PREFIX}01",
        quantity_kg=50.0,
        is_finalized=True,
        finalized_at=datetime.now(UTC),
    )
    session.add(lot)
    session.commit()

    clh = CollectionLotHarvest(collection_lot_id=lot.id, harvest_id=harvest1.id, quantity_used_kg=50.0)
    session.add(clh)

    batch = Batch(
        batch_code=f"{TEST_BATCH_PREFIX}lineage",
        processor_id=processor.id,
        is_finalized=True,
        finalized_at=datetime.now(UTC),
    )
    session.add(batch)
    session.commit()

    bcl = BatchCollectionLot(batch_id=batch.id, collection_lot_id=lot.id, quantity_used_kg=50.0)
    session.add(bcl)
    session.commit()

    # Upload evidence to batch
    cert_id = f"{TEST_CERT_PREFIX}lineage_cert"
    upload_resp = client.post(
        f"/batches/{batch.id}/lab-evidence",
        headers=_auth_headers(processor),
        data={"certificate_id": cert_id, "test_summary": "Lineage test"},
        files={"file": ("lineage_cert.pdf", io.BytesIO(b"%PDF-1.4 lineage"), "application/pdf")},
    )
    assert upload_resp.status_code == 201
    evidence_id = upload_resp.json()["id"]

    db_ev = session.scalar(select(LabEvidence).where(LabEvidence.id == UUID(evidence_id)))
    if db_ev:
        _track_file(db_ev.file_path)

    # bk1 has honey in the batch -> 200 OK for list, detail, download, verify
    r_bk1_list = client.get(f"/batches/{batch.id}/lab-evidence", headers=_auth_headers(bk1))
    assert r_bk1_list.status_code == 200

    r_bk1_detail = client.get(f"/lab-evidence/{evidence_id}", headers=_auth_headers(bk1))
    assert r_bk1_detail.status_code == 200

    r_bk1_download = client.get(f"/lab-evidence/{evidence_id}/download", headers=_auth_headers(bk1))
    assert r_bk1_download.status_code == 200

    r_bk1_verify = client.get(f"/lab-evidence/{evidence_id}/verify", headers=_auth_headers(bk1))
    assert r_bk1_verify.status_code == 200
    assert r_bk1_verify.json()["is_hash_verified"] is True

    # bk2 has NO honey in the batch -> 403 FORBIDDEN for list, detail, download, verify
    r_bk2_list = client.get(f"/batches/{batch.id}/lab-evidence", headers=_auth_headers(bk2))
    assert r_bk2_list.status_code == 403

    r_bk2_detail = client.get(f"/lab-evidence/{evidence_id}", headers=_auth_headers(bk2))
    assert r_bk2_detail.status_code == 403

    r_bk2_download = client.get(f"/lab-evidence/{evidence_id}/download", headers=_auth_headers(bk2))
    assert r_bk2_download.status_code == 403

    r_bk2_verify = client.get(f"/lab-evidence/{evidence_id}/verify", headers=_auth_headers(bk2))
    assert r_bk2_verify.status_code == 403


# ===========================================================================
# 8. Immutability (No PUT, PATCH, DELETE)
# ===========================================================================

def test_immutability_and_forbidden_mutations(session: Session) -> None:
    client = TestClient(app)
    admin = _create_user(session, email=f"{TEST_EMAIL_PREFIX}immut_admin@example.com", role=UserRole.ADMIN)
    fake_id = uuid4()

    # Verify absence / rejection of update and delete endpoints
    assert client.put(f"/lab-evidence/{fake_id}", headers=_auth_headers(admin), json={}).status_code in (404, 405)
    assert client.patch(f"/lab-evidence/{fake_id}", headers=_auth_headers(admin), json={}).status_code in (404, 405)
    assert client.delete(f"/lab-evidence/{fake_id}", headers=_auth_headers(admin)).status_code in (404, 405)


def test_zero_blockchain_interaction_in_lab_module() -> None:
    """Verify statically that addEvidence and linkPackaging are never imported or invoked in app/lab/."""
    from pathlib import Path

    lab_dir = Path(__file__).resolve().parent.parent / "app" / "lab"
    for py_file in lab_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert "addEvidence" not in content
        assert "add_evidence" not in content
        assert "linkPackaging" not in content
        assert "link_packaging" not in content
