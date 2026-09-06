"""Comprehensive API and service integration tests for blockchain endpoints."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from pydantic import SecretStr
import pytest
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.auth.security import create_access_token, hash_password
from app.blockchain import (
    BlockchainClientError,
    BlockchainRecordResponse,
    BlockchainService,
    BlockchainSettings,
    EthereumJsonRpcAdapter,
    MockBlockchainClient,
    UnconfiguredBlockchainClient,
    get_blockchain_service,
)
from app.blockchain.router import get_service
from app.core.database import SessionLocal
from app.main import app
from app.models.audit import AuditEvent
from app.models.enums import BatchStatus, BlockchainStatus, LabEvidenceStatus, UserRole
from app.models.evidence import BlockchainRecord, LabEvidence
from app.models.identity import User
from app.models.traceability import Batch

TEST_EMAIL_PREFIX = "test-bcapi-"
TEST_BATCH_PREFIX = "BCAPI-BAT-"
TEST_CERT_PREFIX = "BCAPI-CERT-"


def _cleanup(database_session: Session) -> None:
    batch_ids = database_session.scalars(
        select(Batch.id).where(Batch.batch_code.like(f"{TEST_BATCH_PREFIX}%"))
    ).all()
    user_ids = database_session.scalars(
        select(User.id).where(User.email.like(f"{TEST_EMAIL_PREFIX}%"))
    ).all()
    lab_ids = database_session.scalars(
        select(LabEvidence.id).where(LabEvidence.certificate_id.like(f"{TEST_CERT_PREFIX}%"))
    ).all()

    bc_conditions = []
    if batch_ids:
        bc_conditions.append(BlockchainRecord.batch_id.in_(batch_ids))
    if lab_ids:
        bc_conditions.append(BlockchainRecord.lab_evidence_id.in_(lab_ids))
    bc_ids = []
    if bc_conditions:
        bc_ids = database_session.scalars(
            select(BlockchainRecord.id).where(or_(*bc_conditions))
        ).all()

    if bc_ids:
        database_session.execute(delete(BlockchainRecord).where(BlockchainRecord.id.in_(bc_ids)))

    # Scoped AuditEvents
    audit_conditions = []
    if user_ids:
        audit_conditions.append(AuditEvent.actor_user_id.in_(user_ids))
    all_entity_ids = set(batch_ids) | set(lab_ids) | set(bc_ids)
    if all_entity_ids:
        audit_conditions.append(AuditEvent.entity_id.in_(list(all_entity_ids)))
    if audit_conditions:
        database_session.execute(delete(AuditEvent).where(or_(*audit_conditions)))

    if lab_ids:
        database_session.execute(delete(LabEvidence).where(LabEvidence.id.in_(lab_ids)))
    if batch_ids:
        database_session.execute(delete(Batch).where(Batch.id.in_(batch_ids)))
    if user_ids:
        database_session.execute(delete(User).where(User.id.in_(user_ids)))
    database_session.commit()


@pytest.fixture
def session() -> Generator[Session, None, None]:
    if SessionLocal is None:
        pytest.skip("HONEY_CHAIN_DATABASE_URL is not configured.")
    with SessionLocal() as db_session:
        _cleanup(db_session)
        yield db_session
        _cleanup(db_session)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


def _create_user(session: Session, email: str, role: UserRole) -> User:
    user = User(
        id=uuid4(),
        name=f"Test {role.value}",
        email=email.lower(),
        password_hash=hash_password("Secret123!"),
        role=role,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(subject=user.id, role=user.role)
    return {"Authorization": f"Bearer {token}"}


def _create_batch(session: Session, batch_code: str, processor: User) -> Batch:
    batch = Batch(
        id=uuid4(),
        batch_code=batch_code,
        processor_id=processor.id,
        status=BatchStatus.ACTIVE,
        created_at=datetime.now(UTC),
    )
    session.add(batch)
    session.commit()
    session.refresh(batch)
    return batch


def _create_lab_evidence(session: Session, batch: Batch, cert_id: str) -> LabEvidence:
    evidence = LabEvidence(
        id=uuid4(),
        batch_id=batch.id,
        certificate_id=cert_id,
        test_summary="Pure clover honey lab test",
        file_name=f"{cert_id}.pdf",
        file_path=f"uploads/{cert_id}.pdf",
        file_hash_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        status=LabEvidenceStatus.ACTIVE,
        uploaded_at=datetime.now(UTC),
    )
    session.add(evidence)
    session.commit()
    session.refresh(evidence)
    return evidence


# ===========================================================================
# 1. Runtime Selection Tests
# ===========================================================================

def test_runtime_selection_configured_selects_adapter() -> None:
    settings = BlockchainSettings(
        enabled=True,
        rpc_url="http://127.0.0.1:8545",
        contract_address="0x5FbDB2315678afecb367f032d93F642f64180aa3",
        chain_id=31337,
        network_name="hardhat-local",
        private_key=SecretStr("0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"),
    )
    assert settings.is_configured() is True
    service = BlockchainService(settings=settings)
    assert isinstance(service.client, EthereumJsonRpcAdapter)


def test_runtime_selection_unconfigured_selects_unconfigured_client() -> None:
    settings = BlockchainSettings(enabled=False)
    assert settings.is_configured() is False
    service = BlockchainService(settings=settings)
    assert isinstance(service.client, UnconfiguredBlockchainClient)


def test_explicit_mock_blockchain_client_injection_works() -> None:
    mock_client = MockBlockchainClient(network_name="mock-test-chain")
    service = BlockchainService(client=mock_client)
    assert service.client is mock_client
    assert isinstance(service.client, MockBlockchainClient)


# ===========================================================================
# 2. Authenticated Actor Attribution
# ===========================================================================

def test_authenticated_actor_uuid_stored_in_audit_event(session: Session) -> None:
    processor = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-actor@example.com", UserRole.PROCESSOR)
    admin = _create_user(session, f"{TEST_EMAIL_PREFIX}admin-actor@example.com", UserRole.ADMIN)
    batch = _create_batch(session, f"{TEST_BATCH_PREFIX}ACTOR-001", processor)
    evidence = _create_lab_evidence(session, batch, f"{TEST_CERT_PREFIX}ACTOR-001")

    mock_client = MockBlockchainClient(network_name="test-net")
    service = BlockchainService(client=mock_client)

    # 1. Admin registers batch: actor should be admin.id, NOT processor.id
    record = service.register_batch_on_chain(session, batch.id, actor_user_id=admin.id)
    audit = session.scalar(
        select(AuditEvent).where(
            AuditEvent.entity_type == "BLOCKCHAIN_RECORD",
            AuditEvent.entity_id == record.id,
        )
    )
    assert audit is not None
    assert audit.actor_user_id == admin.id
    assert audit.actor_user_id != processor.id
    assert audit.metadata_json["batch_id"] == str(batch.id)
    assert audit.metadata_json["batch_code"] == batch.batch_code

    # 2. Admin adds evidence: actor should be admin.id
    ev_record = service.add_evidence_on_chain(session, evidence.id, actor_user_id=admin.id)
    ev_audit = session.scalar(
        select(AuditEvent).where(
            AuditEvent.entity_type == "BLOCKCHAIN_RECORD",
            AuditEvent.entity_id == ev_record.id,
        )
    )
    assert ev_audit is not None
    assert ev_audit.actor_user_id == admin.id
    assert ev_audit.metadata_json["evidence_id"] == str(evidence.id)
    assert ev_audit.metadata_json["certificate_id"] == evidence.certificate_id


# ===========================================================================
# 3. FastAPI API Router Endpoints & Permissions
# ===========================================================================

def test_admin_can_invoke_blockchain_batch_and_evidence(
    session: Session, client: TestClient
) -> None:
    processor = _create_user(session, f"{TEST_EMAIL_PREFIX}proc1@example.com", UserRole.PROCESSOR)
    admin = _create_user(session, f"{TEST_EMAIL_PREFIX}admin1@example.com", UserRole.ADMIN)
    batch = _create_batch(session, f"{TEST_BATCH_PREFIX}ADM-001", processor)
    evidence = _create_lab_evidence(session, batch, f"{TEST_CERT_PREFIX}ADM-001")

    mock_client = MockBlockchainClient(network_name="mock-chain")
    mock_service = BlockchainService(client=mock_client)
    app.dependency_overrides[get_service] = lambda: mock_service

    try:
        # Admin registers batch
        res_batch = client.post(
            f"/batches/{batch.id}/blockchain-register",
            headers=_auth_headers(admin),
        )
        assert res_batch.status_code == 201
        data_batch = res_batch.json()
        assert data_batch["batch_id"] == str(batch.id)
        assert data_batch["event_type"] == "BATCH_REGISTERED"
        assert data_batch["status"] == "CONFIRMED"
        assert data_batch["transaction_hash"].startswith("0x")

        # Admin records evidence
        res_ev = client.post(
            f"/lab-evidence/{evidence.id}/blockchain-record",
            headers=_auth_headers(admin),
        )
        assert res_ev.status_code == 201
        data_ev = res_ev.json()
        assert data_ev["lab_evidence_id"] == str(evidence.id)
        assert data_ev["event_type"] == "LAB_EVIDENCE_RECORDED"
        assert data_ev["status"] == "CONFIRMED"

        # Check AuditEvents recorded admin as actor
        audits = session.scalars(
            select(AuditEvent).where(AuditEvent.entity_type == "BLOCKCHAIN_RECORD")
        ).all()
        assert len(audits) == 2
        assert all(a.actor_user_id == admin.id for a in audits)
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_authorized_processor_can_invoke_blockchain_operations(
    session: Session, client: TestClient
) -> None:
    processor = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-owner@example.com", UserRole.PROCESSOR)
    batch = _create_batch(session, f"{TEST_BATCH_PREFIX}OWN-001", processor)
    evidence = _create_lab_evidence(session, batch, f"{TEST_CERT_PREFIX}OWN-001")

    mock_client = MockBlockchainClient(network_name="mock-chain")
    mock_service = BlockchainService(client=mock_client)
    app.dependency_overrides[get_service] = lambda: mock_service

    try:
        # Processor registers own batch
        res_batch = client.post(
            f"/batches/{batch.id}/blockchain-register",
            headers=_auth_headers(processor),
        )
        assert res_batch.status_code == 201
        assert res_batch.json()["status"] == "CONFIRMED"

        # Processor records own evidence
        res_ev = client.post(
            f"/lab-evidence/{evidence.id}/blockchain-record",
            headers=_auth_headers(processor),
        )
        assert res_ev.status_code == 201
        assert res_ev.json()["status"] == "CONFIRMED"
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_beekeeper_cannot_write_blockchain_records(
    session: Session, client: TestClient
) -> None:
    processor = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-bk@example.com", UserRole.PROCESSOR)
    beekeeper = _create_user(session, f"{TEST_EMAIL_PREFIX}beekeeper@example.com", UserRole.BEEKEEPER)
    batch = _create_batch(session, f"{TEST_BATCH_PREFIX}BK-001", processor)
    evidence = _create_lab_evidence(session, batch, f"{TEST_CERT_PREFIX}BK-001")

    mock_client = MockBlockchainClient(network_name="mock-chain")
    app.dependency_overrides[get_service] = lambda: BlockchainService(client=mock_client)

    try:
        res_batch = client.post(
            f"/batches/{batch.id}/blockchain-register",
            headers=_auth_headers(beekeeper),
        )
        assert res_batch.status_code == 403
        assert res_batch.json()["detail"] == "Insufficient permissions"

        res_ev = client.post(
            f"/lab-evidence/{evidence.id}/blockchain-record",
            headers=_auth_headers(beekeeper),
        )
        assert res_ev.status_code == 403
        assert res_ev.json()["detail"] == "Insufficient permissions"
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_cross_domain_unauthorized_access_rejected(
    session: Session, client: TestClient
) -> None:
    proc1 = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-one@example.com", UserRole.PROCESSOR)
    proc2 = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-two@example.com", UserRole.PROCESSOR)
    batch = _create_batch(session, f"{TEST_BATCH_PREFIX}PROC1-001", proc1)
    evidence = _create_lab_evidence(session, batch, f"{TEST_CERT_PREFIX}PROC1-001")

    mock_client = MockBlockchainClient(network_name="mock-chain")
    app.dependency_overrides[get_service] = lambda: BlockchainService(client=mock_client)

    try:
        # Processor 2 attempts to register Processor 1's batch
        res_batch = client.post(
            f"/batches/{batch.id}/blockchain-register",
            headers=_auth_headers(proc2),
        )
        assert res_batch.status_code == 403
        assert "Processors can only register their own batches" in res_batch.json()["detail"]

        # Processor 2 attempts to record evidence for Processor 1's batch
        res_ev = client.post(
            f"/lab-evidence/{evidence.id}/blockchain-record",
            headers=_auth_headers(proc2),
        )
        assert res_ev.status_code == 403
        assert "Processors can only record lab evidence for their own batches" in res_ev.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_blockchain_failure_does_not_create_false_confirmed_record(
    session: Session, client: TestClient
) -> None:
    admin = _create_user(session, f"{TEST_EMAIL_PREFIX}admin-fail@example.com", UserRole.ADMIN)
    processor = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-fail@example.com", UserRole.PROCESSOR)
    batch = _create_batch(session, f"{TEST_BATCH_PREFIX}FAIL-001", processor)

    failing_client = MockBlockchainClient(
        network_name="mock-fail",
        simulate_failure=True,
        failure_error_message="Gas limit exceeded or reverted",
    )
    app.dependency_overrides[get_service] = lambda: BlockchainService(client=failing_client)

    try:
        res = client.post(
            f"/batches/{batch.id}/blockchain-register",
            headers=_auth_headers(admin),
        )
        assert res.status_code == 502
        assert "Blockchain transaction failed or was reverted on-chain" in res.json()["detail"]

        # Verify DB does NOT have a CONFIRMED record
        records = session.scalars(
            select(BlockchainRecord).where(BlockchainRecord.batch_id == batch.id)
        ).all()
        assert len(records) == 1
        assert records[0].status == BlockchainStatus.FAILED
        assert records[0].status != BlockchainStatus.CONFIRMED
        assert records[0].transaction_hash is None
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_batch_blockchain_records_get_endpoint(
    session: Session, client: TestClient
) -> None:
    proc1 = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-get1@example.com", UserRole.PROCESSOR)
    proc2 = _create_user(session, f"{TEST_EMAIL_PREFIX}proc-get2@example.com", UserRole.PROCESSOR)
    admin = _create_user(session, f"{TEST_EMAIL_PREFIX}admin-get@example.com", UserRole.ADMIN)
    batch = _create_batch(session, f"{TEST_BATCH_PREFIX}GET-001", proc1)

    mock_client = MockBlockchainClient(network_name="mock-chain")
    mock_service = BlockchainService(client=mock_client)
    app.dependency_overrides[get_service] = lambda: mock_service

    try:
        # Register batch
        reg_res = client.post(
            f"/batches/{batch.id}/blockchain-register",
            headers=_auth_headers(admin),
        )
        assert reg_res.status_code == 201

        # 1. Admin gets records -> 200 OK
        res_admin = client.get(
            f"/batches/{batch.id}/blockchain-records",
            headers=_auth_headers(admin),
        )
        assert res_admin.status_code == 200
        records = res_admin.json()
        assert len(records) == 1
        assert records[0]["batch_id"] == str(batch.id)
        assert records[0]["event_type"] == "BATCH_REGISTERED"

        # 2. Owning processor gets records -> 200 OK
        res_proc1 = client.get(
            f"/batches/{batch.id}/blockchain-records",
            headers=_auth_headers(proc1),
        )
        assert res_proc1.status_code == 200
        assert len(res_proc1.json()) == 1

        # 3. Unrelated processor gets records -> 403 Forbidden
        res_proc2 = client.get(
            f"/batches/{batch.id}/blockchain-records",
            headers=_auth_headers(proc2),
        )
        assert res_proc2.status_code == 403

        # 4. Non-existent batch -> 404 Not Found
        res_missing = client.get(
            f"/batches/{uuid4()}/blockchain-records",
            headers=_auth_headers(admin),
        )
        assert res_missing.status_code == 404
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_blockchain_api_cleanup_preserves_sentinel_data(session: Session) -> None:
    """Validate that scoped cleanup does NOT delete unrelated sentinel blockchain records."""
    sentinel_user = User(
        id=uuid4(),
        name="Sentinel User",
        email=f"sentinel-{uuid4().hex[:8]}@example.test",
        password_hash=hash_password("SentinelPass123!"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    session.add(sentinel_user)
    session.commit()

    sentinel_batch = Batch(
        id=uuid4(),
        batch_code=f"SENTINEL-BAT-{uuid4().hex[:8]}",
        status=BatchStatus.ACTIVE,
        is_finalized=True,
        finalized_at=datetime.now(UTC),
        processor_id=sentinel_user.id,
    )
    session.add(sentinel_batch)
    session.commit()

    sentinel_record = BlockchainRecord(
        id=uuid4(),
        batch_id=sentinel_batch.id,
        event_type="BATCH_FINALIZED",
        status=BlockchainStatus.CONFIRMED,
        network="hardhat",
        transaction_hash=f"0x{uuid4().hex}{uuid4().hex}",
        recorded_at=datetime.now(UTC),
    )
    session.add(sentinel_record)
    session.commit()

    sentinel_audit = AuditEvent(
        id=uuid4(),
        event_type="SENTINEL_EVENT",
        entity_type="BLOCKCHAIN_RECORD",
        entity_id=sentinel_record.id,
        actor_user_id=sentinel_user.id,
        timestamp=datetime.now(UTC),
    )
    session.add(sentinel_audit)
    session.commit()

    try:
        _cleanup(session)

        surviving_user = session.get(User, sentinel_user.id)
        assert surviving_user is not None
        assert surviving_user.id == sentinel_user.id

        surviving_batch = session.get(Batch, sentinel_batch.id)
        assert surviving_batch is not None
        assert surviving_batch.id == sentinel_batch.id

        surviving_record = session.get(BlockchainRecord, sentinel_record.id)
        assert surviving_record is not None
        assert surviving_record.id == sentinel_record.id

        surviving_audit = session.get(AuditEvent, sentinel_audit.id)
        assert surviving_audit is not None
        assert surviving_audit.id == sentinel_audit.id
    finally:
        session.execute(delete(AuditEvent).where(AuditEvent.id == sentinel_audit.id))
        session.execute(delete(BlockchainRecord).where(BlockchainRecord.id == sentinel_record.id))
        session.execute(delete(Batch).where(Batch.id == sentinel_batch.id))
        session.execute(delete(User).where(User.id == sentinel_user.id))
        session.commit()
