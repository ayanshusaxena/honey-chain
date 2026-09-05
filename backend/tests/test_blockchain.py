"""Comprehensive tests for the blockchain adapter, cryptographic mapping, and service layer."""

from __future__ import annotations

import hashlib
from collections.abc import Generator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.blockchain import (
    EMPTY_METADATA_HASH,
    EMPTY_METADATA_HASH_HEX,
    AddEvidencePayload,
    BlockchainClientError,
    BlockchainNotConfiguredError,
    BlockchainService,
    BlockchainSettings,
    EthereumJsonRpcAdapter,
    HONEY_TRACEABILITY_ABI,
    MockBlockchainClient,
    UnconfiguredBlockchainClient,
    bytes32_to_hex,
    sha256_hex_to_bytes32,
)
from app.core.database import SessionLocal
from app.models.audit import AuditEvent
from app.models.enums import BatchStatus, BlockchainStatus, LabEvidenceStatus, UserRole
from app.models.evidence import BlockchainRecord, LabEvidence
from app.models.identity import User
from app.models.traceability import Batch

TEST_EMAIL_PREFIX = "test-bc-"
TEST_BATCH_PREFIX = "BC-BAT-"
TEST_CERT_PREFIX = "BC-CERT-"


def _cleanup(database_session: Session) -> None:
    database_session.execute(delete(AuditEvent).where(AuditEvent.entity_type == "BLOCKCHAIN_RECORD"))
    database_session.execute(delete(BlockchainRecord))
    database_session.execute(delete(LabEvidence).where(LabEvidence.certificate_id.like(f"{TEST_CERT_PREFIX}%")))
    database_session.execute(delete(Batch).where(Batch.batch_code.like(f"{TEST_BATCH_PREFIX}%")))
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


def _create_user(session: Session, *, email: str, role: UserRole) -> User:
    user = User(
        name=f"Test {role.value}",
        email=email.lower(),
        password_hash=hash_password("secure-test-pass"),
        role=role,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _create_batch(session: Session, *, batch_code: str, processor: User) -> Batch:
    batch = Batch(
        batch_code=batch_code,
        processor_id=processor.id,
        status=BatchStatus.ACTIVE,
        is_finalized=False,
    )
    session.add(batch)
    session.commit()
    session.refresh(batch)
    return batch


def _create_lab_evidence(session: Session, *, batch: Batch, certificate_id: str, file_hash_sha256: str) -> LabEvidence:
    evidence = LabEvidence(
        id=uuid4(),
        batch_id=batch.id,
        certificate_id=certificate_id,
        test_summary="Sample laboratory certificate for blockchain test.",
        file_name="lab_report.pdf",
        file_path=f"backend/uploads/lab_evidence/{certificate_id}.pdf",
        file_hash_sha256=file_hash_sha256,
        status=LabEvidenceStatus.ACTIVE,
        uploaded_at=datetime.now(UTC),
    )
    session.add(evidence)
    session.commit()
    session.refresh(evidence)
    return evidence


# ===========================================================================
# 1. Cryptographic Hash Conversion (LOCKED RULES)
# ===========================================================================

def test_sha256_hex_to_bytes32_conversion_preserves_exact_bytes() -> None:
    """Verify known SHA-256 hex converts to exact 32-byte digest with zero rehashing."""
    raw_payload = b"%PDF-1.4 Known PDF byte content for cryptographic test"
    computed_sha256 = hashlib.sha256(raw_payload).hexdigest().lower()

    # Convert using adapter utility
    bytes32_val = sha256_hex_to_bytes32(computed_sha256)

    # 1. Exact 32 bytes length
    assert len(bytes32_val) == 32
    assert isinstance(bytes32_val, bytes)

    # 2. Exact match with standard library bytes.fromhex (NO second hash)
    assert bytes32_val == bytes.fromhex(computed_sha256)

    # 3. Prove NO rehashing took place:
    # If the hex string had been hashed again (SHA-256 or Keccak), it would NOT equal bytes.fromhex(computed_sha256)
    rehashed_sha256 = hashlib.sha256(computed_sha256.encode()).digest()
    assert bytes32_val != rehashed_sha256

    # 4. Roundtrip back to hex
    assert bytes32_to_hex(bytes32_val) == f"0x{computed_sha256}"


def test_sha256_hex_to_bytes32_accepts_0x_prefix() -> None:
    raw_hex = "a" * 64
    b1 = sha256_hex_to_bytes32(raw_hex)
    b2 = sha256_hex_to_bytes32(f"0x{raw_hex}")
    assert b1 == b2
    assert len(b1) == 32


def test_sha256_hex_to_bytes32_rejects_invalid_inputs() -> None:
    # Too short
    with pytest.raises(ValueError, match="64 hexadecimal characters"):
        sha256_hex_to_bytes32("abc123")

    # Too long
    with pytest.raises(ValueError, match="64 hexadecimal characters"):
        sha256_hex_to_bytes32("a" * 65)

    # Invalid characters
    with pytest.raises(ValueError, match="64 hexadecimal characters"):
        sha256_hex_to_bytes32("g" * 64)

    # Non-string
    with pytest.raises(ValueError, match="Expected hex string"):
        sha256_hex_to_bytes32(12345)  # type: ignore[arg-type]


def test_metadata_hash_is_canonical_bytes32_zero() -> None:
    """Verify metadataHash is fixed to bytes32(0)."""
    assert len(EMPTY_METADATA_HASH) == 32
    assert EMPTY_METADATA_HASH == b"\x00" * 32
    assert bytes32_to_hex(EMPTY_METADATA_HASH) == "0x" + "00" * 32
    assert EMPTY_METADATA_HASH_HEX == "0x" + "00" * 32


# ===========================================================================
# 2. Batch Registration (LOCKED: Batch.batch_code, never Batch.id)
# ===========================================================================

def test_batch_registration_uses_batch_code_and_zero_metadata_hash(session: Session) -> None:
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}proc1@example.com", role=UserRole.PROCESSOR)
    batch = _create_batch(session, batch_code=f"{TEST_BATCH_PREFIX}001", processor=processor)

    mock_client = MockBlockchainClient(network_name="test-net")
    service = BlockchainService(client=mock_client)

    record = service.register_batch_on_chain(session, batch.id)

    # 1. Verify mock client received Batch.batch_code (NOT Batch.id)
    assert len(mock_client.registered_batches) == 1
    call = mock_client.registered_batches[0]
    assert call.batch_code == batch.batch_code
    assert call.batch_code != str(batch.id)

    # 2. Verify metadataHash is exactly bytes32(0)
    assert call.metadata_hash == EMPTY_METADATA_HASH
    assert call.metadata_hash == b"\x00" * 32

    # 3. Verify BlockchainRecord saved in PostgreSQL
    assert record.batch_id == batch.id
    assert record.lab_evidence_id is None
    assert record.event_type == "BATCH_REGISTERED"
    assert record.status == BlockchainStatus.CONFIRMED
    assert record.network == "test-net"
    assert record.transaction_hash.startswith("0x")

    # 4. Verify AuditEvent logged
    audit = session.scalar(
        select(AuditEvent).where(
            AuditEvent.event_type == "BLOCKCHAIN_BATCH_REGISTERED",
            AuditEvent.entity_id == record.id,
        )
    )
    assert audit is not None
    assert audit.metadata_json["batch_code"] == batch.batch_code


def test_batch_registration_fails_for_nonexistent_batch(session: Session) -> None:
    mock_client = MockBlockchainClient()
    service = BlockchainService(client=mock_client)

    with pytest.raises(ValueError, match="not found"):
        service.register_batch_on_chain(session, uuid4())


# ===========================================================================
# 3. LabEvidence Hash Recording (LOCKED: exact 32-byte digest, no rehash)
# ===========================================================================

def test_record_evidence_maps_file_hash_sha256_to_exact_bytes32(session: Session) -> None:
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}proc2@example.com", role=UserRole.PROCESSOR)
    batch = _create_batch(session, batch_code=f"{TEST_BATCH_PREFIX}002", processor=processor)

    # Create known 64-char SHA-256 hash
    sample_pdf = b"%PDF-1.4 Certified Honey Lab Report"
    expected_sha256_hex = hashlib.sha256(sample_pdf).hexdigest().lower()
    expected_bytes32 = bytes.fromhex(expected_sha256_hex)

    evidence = _create_lab_evidence(
        session,
        batch=batch,
        certificate_id=f"{TEST_CERT_PREFIX}002",
        file_hash_sha256=expected_sha256_hex,
    )

    mock_client = MockBlockchainClient(network_name="sepolia-mock")
    service = BlockchainService(client=mock_client)

    record = service.record_evidence_on_chain(session, evidence.id)

    # 1. Verify client received exact 32-byte digest matching file_hash_sha256
    assert len(mock_client.recorded_evidences) == 1
    call = mock_client.recorded_evidences[0]
    assert call.batch_code == batch.batch_code
    assert call.evidence_hash == expected_bytes32
    assert len(call.evidence_hash) == 32

    # 2. Verify BlockchainRecord saved in PostgreSQL
    assert record.batch_id == batch.id
    assert record.lab_evidence_id == evidence.id
    assert record.event_type == "LAB_EVIDENCE_RECORDED"
    assert record.status == BlockchainStatus.CONFIRMED
    assert record.network == "sepolia-mock"
    assert record.transaction_hash.startswith("0x")

    # 3. Verify AuditEvent logged
    audit = session.scalar(
        select(AuditEvent).where(
            AuditEvent.event_type == "BLOCKCHAIN_EVIDENCE_RECORDED",
            AuditEvent.entity_id == record.id,
        )
    )
    assert audit is not None
    assert audit.metadata_json["certificate_id"] == evidence.certificate_id
    assert audit.metadata_json["file_hash_sha256"] == expected_sha256_hex


def test_record_evidence_fails_for_nonexistent_evidence(session: Session) -> None:
    mock_client = MockBlockchainClient()
    service = BlockchainService(client=mock_client)

    with pytest.raises(ValueError, match="Lab evidence with ID.*not found"):
        service.record_evidence_on_chain(session, uuid4())


# ===========================================================================
# 4. Unconfigured & Error Handling Scenarios
# ===========================================================================

def test_unconfigured_client_raises_blockchain_not_configured_error(session: Session) -> None:
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}proc3@example.com", role=UserRole.PROCESSOR)
    batch = _create_batch(session, batch_code=f"{TEST_BATCH_PREFIX}003", processor=processor)

    unconfigured_client = UnconfiguredBlockchainClient()
    service = BlockchainService(client=unconfigured_client)

    with pytest.raises(BlockchainNotConfiguredError, match="not configured or disabled"):
        service.register_batch_on_chain(session, batch.id)


def test_client_failure_translates_to_backend_error_and_records_failed_status(session: Session) -> None:
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}proc4@example.com", role=UserRole.PROCESSOR)
    batch = _create_batch(session, batch_code=f"{TEST_BATCH_PREFIX}004", processor=processor)

    failing_client = MockBlockchainClient(
        simulate_failure=True,
        failure_error_message="Gas limit exceeded or node unreachable",
    )
    service = BlockchainService(client=failing_client)

    with pytest.raises(BlockchainClientError, match="Gas limit exceeded"):
        service.register_batch_on_chain(session, batch.id)

    # Verify a failed audit record was logged in PostgreSQL
    failed_record = session.scalar(
        select(BlockchainRecord).where(
            BlockchainRecord.batch_id == batch.id,
            BlockchainRecord.status == BlockchainStatus.FAILED,
        )
    )
    assert failed_record is not None
    assert failed_record.event_type == "BATCH_REGISTERED"
    assert failed_record.transaction_hash is None


# ===========================================================================
# 5. Query Batch Blockchain Records
# ===========================================================================

def test_get_batch_blockchain_records_retrieves_audit_history(session: Session) -> None:
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}proc5@example.com", role=UserRole.PROCESSOR)
    batch = _create_batch(session, batch_code=f"{TEST_BATCH_PREFIX}005", processor=processor)

    evidence = _create_lab_evidence(
        session,
        batch=batch,
        certificate_id=f"{TEST_CERT_PREFIX}005",
        file_hash_sha256="c" * 64,
    )

    mock_client = MockBlockchainClient()
    service = BlockchainService(client=mock_client)

    # Perform registration and evidence recording
    service.register_batch_on_chain(session, batch.id)
    service.record_evidence_on_chain(session, evidence.id)

    history = service.get_batch_blockchain_records(session, batch.id)
    assert len(history) == 2
    event_types = [h.event_type for h in history]
    assert "BATCH_REGISTERED" in event_types
    assert "LAB_EVIDENCE_RECORDED" in event_types


def test_db_commit_failure_rolls_back_and_prevents_false_confirmed_state(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify Scenario C: if blockchain succeeds but DB commit fails, session is rolled back with no false CONFIRMED record."""
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}proc6@example.com", role=UserRole.PROCESSOR)
    batch = _create_batch(session, batch_code=f"{TEST_BATCH_PREFIX}006", processor=processor)

    mock_client = MockBlockchainClient()
    service = BlockchainService(client=mock_client)

    # Simulate DB commit failure
    def mock_commit(self: Session) -> None:
        raise RuntimeError("Simulated database write error during commit")

    monkeypatch.setattr(Session, "commit", mock_commit)

    with pytest.raises(RuntimeError, match="Simulated database write error"):
        service.register_batch_on_chain(session, batch.id)

    # Clear monkeypatch to query cleanly
    monkeypatch.undo()

    # Verify no false CONFIRMED record exists in PostgreSQL
    records = session.scalars(
        select(BlockchainRecord).where(BlockchainRecord.batch_id == batch.id)
    ).all()
    assert len(records) == 0


# ===========================================================================
# 6. Solidity Alignment & Contract ABI Verification
# ===========================================================================

def test_add_evidence_on_chain_aligns_with_solidity_add_evidence(session: Session) -> None:
    """Verify add_evidence_on_chain calls add_evidence and records AddEvidencePayload."""
    processor = _create_user(session, email=f"{TEST_EMAIL_PREFIX}proc7@example.com", role=UserRole.PROCESSOR)
    batch = _create_batch(session, batch_code=f"{TEST_BATCH_PREFIX}007", processor=processor)

    sample_pdf = b"%PDF-1.4 Lab Certificate For Alignment Test"
    expected_sha256_hex = hashlib.sha256(sample_pdf).hexdigest().lower()
    expected_bytes32 = bytes.fromhex(expected_sha256_hex)

    evidence = _create_lab_evidence(
        session,
        batch=batch,
        certificate_id=f"{TEST_CERT_PREFIX}007",
        file_hash_sha256=expected_sha256_hex,
    )

    mock_client = MockBlockchainClient(network_name="sepolia-mock")
    service = BlockchainService(client=mock_client)

    # Call new add_evidence_on_chain method
    record = service.add_evidence_on_chain(session, evidence.id)

    assert len(mock_client.added_evidences) == 1
    call = mock_client.added_evidences[0]
    assert isinstance(call, AddEvidencePayload)
    assert call.batch_code == batch.batch_code
    assert call.evidence_hash == expected_bytes32
    assert len(call.evidence_hash) == 32

    # Verify backward compatibility property
    assert mock_client.recorded_evidences[0] == call
    assert record.status == BlockchainStatus.CONFIRMED


def test_abi_specification_and_solidity_interface_compliance() -> None:
    """Verify backend HONEY_TRACEABILITY_ABI matches exact compiled Solidity artifact."""
    assert len(HONEY_TRACEABILITY_ABI) == 18

    functions = {item["name"]: item for item in HONEY_TRACEABILITY_ABI if item.get("type") == "function"}
    events = {item["name"]: item for item in HONEY_TRACEABILITY_ABI if item.get("type") == "event"}

    # 1. Verify exact write functions
    assert "registerBatch" in functions
    assert [i["type"] for i in functions["registerBatch"]["inputs"]] == ["string", "bytes32"]

    assert "addEvidence" in functions
    assert [i["type"] for i in functions["addEvidence"]["inputs"]] == ["string", "bytes32"]

    assert "linkPackaging" in functions
    assert [i["type"] for i in functions["linkPackaging"]["inputs"]] == ["string", "string"]

    assert "updateStatus" in functions
    assert [i["type"] for i in functions["updateStatus"]["inputs"]] == ["string", "uint8"]

    # 2. Verify view functions
    assert "getBatch" in functions
    assert "getEvidenceCount" in functions
    assert "getEvidence" in functions
    assert "owner" in functions

    # 3. Verify events
    assert "BatchRegistered" in events
    assert "EvidenceAdded" in events
    assert "PackagingLinked" in events
    assert "StatusUpdated" in events


def test_ethereum_json_rpc_adapter_defaults_to_compiled_abi() -> None:
    """Verify EthereumJsonRpcAdapter automatically uses HONEY_TRACEABILITY_ABI."""
    settings = BlockchainSettings(
        rpc_url="http://localhost:8545",
        contract_address="0x5FbDB2315678afecb367f032d93F642f64180aa3",
        enabled=True,
    )
    adapter = EthereumJsonRpcAdapter(settings=settings)
    assert adapter.contract_abi == HONEY_TRACEABILITY_ABI
    assert adapter.is_configured() is True
