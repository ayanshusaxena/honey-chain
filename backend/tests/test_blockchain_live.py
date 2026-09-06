"""Integration tests for EthereumJsonRpcAdapter against a live EVM node (e.g. Hardhat).

These tests run against a running JSON-RPC node (default http://127.0.0.1:8545).
If the node is not running or unreachable, tests are cleanly skipped to preserve
fast, isolated unit testing without external network/daemon requirements.
"""

from __future__ import annotations

from datetime import UTC, datetime
import os
import socket
from urllib.parse import urlparse
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import SecretStr
import pytest
from sqlalchemy import delete, select
from web3 import Web3

from app.auth.security import create_access_token, hash_password
from app.blockchain.abi import HONEY_TRACEABILITY_ABI
from app.blockchain.adapter import EthereumJsonRpcAdapter
from app.blockchain.config import BlockchainSettings
from app.blockchain.router import get_service
from app.blockchain.schemas import EMPTY_METADATA_HASH
from app.blockchain.service import BlockchainService
from app.core.database import SessionLocal
from app.main import app
from app.models.audit import AuditEvent
from app.models.enums import BatchStatus, BlockchainStatus, LabEvidenceStatus, UserRole
from app.models.evidence import BlockchainRecord, LabEvidence
from app.models.identity import User
from app.models.traceability import Batch

# Standard local Hardhat node account #0
DEFAULT_HARDHAT_RPC_URL = "http://127.0.0.1:8545"
DEFAULT_HARDHAT_PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
DEFAULT_HARDHAT_DEPLOYER = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
DEFAULT_CONTRACT_ADDRESS = "0x5FbDB2315678afecb367f032d93F642f64180aa3"


def is_live_node_available(rpc_url: str) -> bool:
    """Check if the local RPC port is open and accepting HTTP connections."""
    try:
        parsed = urlparse(rpc_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 8545
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(
    not is_live_node_available(os.getenv("HONEY_CHAIN_BLOCKCHAIN_RPC_URL", DEFAULT_HARDHAT_RPC_URL)),
    reason=f"Live JSON-RPC node not available at {DEFAULT_HARDHAT_RPC_URL}",
)


@pytest.fixture(scope="module")
def live_w3() -> Web3:
    rpc_url = os.getenv("HONEY_CHAIN_BLOCKCHAIN_RPC_URL", DEFAULT_HARDHAT_RPC_URL)
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        pytest.skip(f"Web3 cannot connect to RPC at {rpc_url}")
    return w3


@pytest.fixture(scope="module")
def contract_address(live_w3: Web3) -> str:
    addr = os.getenv("HONEY_CHAIN_BLOCKCHAIN_CONTRACT_ADDRESS", DEFAULT_CONTRACT_ADDRESS)
    checksum_addr = Web3.to_checksum_address(addr)
    code = live_w3.eth.get_code(checksum_addr)
    if not code or code == b"" or code == b"\x00":
        pytest.skip(f"No contract bytecode deployed at {checksum_addr}")
    return checksum_addr


def test_live_node_and_contract_bytecode(live_w3: Web3, contract_address: str) -> None:
    """Verify chain ID, deployed bytecode presence, and contract owner."""
    assert live_w3.eth.chain_id == 31337
    code = live_w3.eth.get_code(contract_address)
    assert len(code) > 0, "Bytecode must be present at contract address"

    contract = live_w3.eth.contract(address=contract_address, abi=HONEY_TRACEABILITY_ABI)
    owner = contract.functions.owner().call()
    assert owner.lower() == DEFAULT_HARDHAT_DEPLOYER.lower()


def test_live_adapter_register_batch_and_add_evidence(
    live_w3: Web3, contract_address: str
) -> None:
    """Verify real transaction submission and on-chain state queries via EthereumJsonRpcAdapter."""
    rpc_url = os.getenv("HONEY_CHAIN_BLOCKCHAIN_RPC_URL", DEFAULT_HARDHAT_RPC_URL)
    priv_key = os.getenv("HONEY_CHAIN_BLOCKCHAIN_PRIVATE_KEY", DEFAULT_HARDHAT_PRIVATE_KEY)

    settings = BlockchainSettings(
        enabled=True,
        rpc_url=rpc_url,
        contract_address=contract_address,
        chain_id=live_w3.eth.chain_id,
        network_name="localhost",
        private_key=SecretStr(priv_key),
    )

    adapter = EthereumJsonRpcAdapter(settings=settings)
    assert adapter.is_configured() is True

    # 1. Register Batch
    unique_batch_code = f"LIVE-BAT-{uuid4().hex[:8].upper()}"
    reg_result = adapter.register_batch(
        batch_code=unique_batch_code,
        metadata_hash=EMPTY_METADATA_HASH,
    )

    assert reg_result.status == BlockchainStatus.CONFIRMED
    assert reg_result.transaction_hash.startswith("0x")
    assert reg_result.block_number is not None
    assert reg_result.block_number > 0
    assert reg_result.contract_address == contract_address

    # 2. Add Evidence
    evidence_digest = bytes.fromhex(
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    ev_result = adapter.add_evidence(
        batch_code=unique_batch_code,
        evidence_hash=evidence_digest,
    )

    assert ev_result.status == BlockchainStatus.CONFIRMED
    assert ev_result.transaction_hash.startswith("0x")
    assert ev_result.block_number is not None

    # 3. On-chain query verification
    contract = live_w3.eth.contract(address=contract_address, abi=HONEY_TRACEABILITY_ABI)

    batch_data = contract.functions.getBatch(unique_batch_code).call()
    batch_id_ret, meta_hash_ret, status_ret, packaging_ref_ret, created_at_ret, exists_ret = batch_data

    assert exists_ret is True
    assert batch_id_ret == unique_batch_code
    assert status_ret == 0  # Status.ACTIVE
    assert meta_hash_ret == EMPTY_METADATA_HASH

    ev_count = contract.functions.getEvidenceCount(unique_batch_code).call()
    assert ev_count == 1

    ev_0 = contract.functions.getEvidence(unique_batch_code, 0).call()
    ev_hash_ret, ev_ts_ret, ev_exists_ret = ev_0
    assert ev_exists_ret is True
    assert ev_hash_ret == evidence_digest
    assert ev_ts_ret > 0


def test_live_api_fastapi_to_ethereum_adapter_flow(
    live_w3: Web3, contract_address: str
) -> None:
    """End-to-end proof: FastAPI Request -> Blockchain router -> Service -> EthereumJsonRpcAdapter -> Hardhat -> PostgreSQL record + AuditEvent."""
    if SessionLocal is None:
        pytest.skip("HONEY_CHAIN_DATABASE_URL is not configured.")

    rpc_url = os.getenv("HONEY_CHAIN_BLOCKCHAIN_RPC_URL", DEFAULT_HARDHAT_RPC_URL)
    priv_key = os.getenv("HONEY_CHAIN_BLOCKCHAIN_PRIVATE_KEY", DEFAULT_HARDHAT_PRIVATE_KEY)

    settings = BlockchainSettings(
        enabled=True,
        rpc_url=rpc_url,
        contract_address=contract_address,
        chain_id=live_w3.eth.chain_id,
        network_name="localhost",
        private_key=SecretStr(priv_key),
    )

    # Wire the real EthereumJsonRpcAdapter into BlockchainService for FastAPI
    live_service = BlockchainService(settings=settings)
    assert isinstance(live_service.client, EthereumJsonRpcAdapter)
    app.dependency_overrides[get_service] = lambda: live_service

    test_batch_code = f"LIVE-API-{uuid4().hex[:8].upper()}"
    test_email = f"test-live-{uuid4().hex[:6]}@example.com"

    try:
        with SessionLocal() as db_session:
            # 1. Setup Admin user and Batch
            admin_user = User(
                id=uuid4(),
                name="Live Test Admin",
                email=test_email,
                password_hash=hash_password("Secret123!"),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db_session.add(admin_user)
            db_session.commit()
            db_session.refresh(admin_user)

            batch = Batch(
                id=uuid4(),
                batch_code=test_batch_code,
                processor_id=admin_user.id,
                status=BatchStatus.ACTIVE,
                created_at=datetime.now(UTC),
            )
            db_session.add(batch)
            db_session.commit()
            db_session.refresh(batch)

            test_sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
            evidence = LabEvidence(
                id=uuid4(),
                batch_id=batch.id,
                certificate_id=f"LIVE-CERT-{uuid4().hex[:8].upper()}",
                test_summary="Live EVM lab test proof",
                file_name="cert.pdf",
                file_path="uploads/cert.pdf",
                file_hash_sha256=test_sha256,
                status=LabEvidenceStatus.ACTIVE,
                uploaded_at=datetime.now(UTC),
            )
            db_session.add(evidence)
            db_session.commit()
            db_session.refresh(evidence)

            token = create_access_token(subject=admin_user.id, role=admin_user.role)
            headers = {"Authorization": f"Bearer {token}"}

            # 2. Invoke FastAPI endpoint for Batch Registration
            with TestClient(app) as test_client:
                response = test_client.post(
                    f"/batches/{batch.id}/blockchain-register",
                    headers=headers,
                )

                assert response.status_code == 201
                body = response.json()
                assert body["batch_id"] == str(batch.id)
                assert body["event_type"] == "BATCH_REGISTERED"
                assert body["status"] == "CONFIRMED"
                assert body["contract_address"] == contract_address
                assert body["transaction_hash"].startswith("0x")
                assert body["block_number"] is not None

                # 3. Query contract on-chain to prove the real node received the batch tx
                contract = live_w3.eth.contract(address=contract_address, abi=HONEY_TRACEABILITY_ABI)
                batch_on_chain = contract.functions.getBatch(test_batch_code).call()
                assert batch_on_chain[5] is True  # exists
                assert batch_on_chain[0] == test_batch_code  # batchId
                assert batch_on_chain[2] == 0  # status == ACTIVE

                # 4. Verify PostgreSQL audit trail for batch registration with authenticated actor UUID
                record = db_session.scalar(
                    select(BlockchainRecord).where(BlockchainRecord.batch_id == batch.id)
                )
                assert record is not None
                assert record.status == BlockchainStatus.CONFIRMED

                audit = db_session.scalar(
                    select(AuditEvent).where(
                        AuditEvent.entity_type == "BLOCKCHAIN_RECORD",
                        AuditEvent.entity_id == record.id,
                    )
                )
                assert audit is not None
                assert audit.actor_user_id == admin_user.id
                assert audit.metadata_json["transaction_hash"] == body["transaction_hash"]

                # 5. Invoke FastAPI endpoint for Lab Evidence Recording
                ev_response = test_client.post(
                    f"/lab-evidence/{evidence.id}/blockchain-record",
                    headers=headers,
                )
                assert ev_response.status_code == 201
                ev_body = ev_response.json()
                assert ev_body["lab_evidence_id"] == str(evidence.id)
                assert ev_body["batch_id"] == str(batch.id)
                assert ev_body["event_type"] == "LAB_EVIDENCE_RECORDED"
                assert ev_body["status"] == "CONFIRMED"
                assert ev_body["contract_address"] == contract_address
                assert ev_body["transaction_hash"].startswith("0x")
                assert ev_body["block_number"] is not None

                # 6. Query contract on-chain to prove the real node received the evidence tx
                ev_count = contract.functions.getEvidenceCount(test_batch_code).call()
                assert ev_count == 1
                ev_on_chain = contract.functions.getEvidence(test_batch_code, 0).call()
                ev_hash_bytes, ev_ts, ev_exists = ev_on_chain
                assert ev_exists is True
                assert ev_hash_bytes == bytes.fromhex(test_sha256)
                assert ev_ts > 0

                # 7. Verify PostgreSQL audit trail for evidence recording with authenticated actor UUID
                ev_record = db_session.scalar(
                    select(BlockchainRecord).where(BlockchainRecord.lab_evidence_id == evidence.id)
                )
                assert ev_record is not None
                assert ev_record.status == BlockchainStatus.CONFIRMED

                ev_audit = db_session.scalar(
                    select(AuditEvent).where(
                        AuditEvent.entity_type == "BLOCKCHAIN_RECORD",
                        AuditEvent.entity_id == ev_record.id,
                    )
                )
                assert ev_audit is not None
                assert ev_audit.actor_user_id == admin_user.id
                assert ev_audit.metadata_json["transaction_hash"] == ev_body["transaction_hash"]
                assert ev_audit.metadata_json["evidence_id"] == str(evidence.id)

                # 8. Query batch records via API GET endpoint (should now contain both records)
                get_res = test_client.get(
                    f"/batches/{batch.id}/blockchain-records",
                    headers=headers,
                )
                assert get_res.status_code == 200
                records_list = get_res.json()
                assert len(records_list) >= 2
                event_types = [r["event_type"] for r in records_list]
                assert "BATCH_REGISTERED" in event_types
                assert "LAB_EVIDENCE_RECORDED" in event_types

            # 9. Targeted cleanup: only delete entities created by this test using their exact IDs
            created_record_ids = [
                r.id for r in [record, ev_record] if r is not None
            ]
            if created_record_ids:
                db_session.execute(
                    delete(AuditEvent).where(
                        AuditEvent.entity_type == "BLOCKCHAIN_RECORD",
                        AuditEvent.entity_id.in_(created_record_ids),
                    )
                )
                db_session.execute(
                    delete(BlockchainRecord).where(
                        BlockchainRecord.id.in_(created_record_ids)
                    )
                )
            db_session.execute(delete(LabEvidence).where(LabEvidence.id == evidence.id))
            db_session.execute(delete(Batch).where(Batch.id == batch.id))
            db_session.execute(delete(User).where(User.id == admin_user.id))
            db_session.commit()
    finally:
        app.dependency_overrides.pop(get_service, None)


def test_live_duplicate_registration_revert_records_failed_status(
    live_w3: Web3, contract_address: str
) -> None:
    """Verify that an on-chain contract revert (e.g. duplicate batch registration)
    is caught by EthereumJsonRpcAdapter as BlockchainTransactionError,
    persisted to PostgreSQL with BlockchainStatus.FAILED, and cleanly reported via API (502).
    """
    if SessionLocal is None:
        pytest.skip("HONEY_CHAIN_DATABASE_URL is not configured.")

    rpc_url = os.getenv("HONEY_CHAIN_BLOCKCHAIN_RPC_URL", DEFAULT_HARDHAT_RPC_URL)
    priv_key = os.getenv("HONEY_CHAIN_BLOCKCHAIN_PRIVATE_KEY", DEFAULT_HARDHAT_PRIVATE_KEY)

    settings = BlockchainSettings(
        enabled=True,
        rpc_url=rpc_url,
        contract_address=contract_address,
        chain_id=live_w3.eth.chain_id,
        network_name="localhost",
        private_key=SecretStr(priv_key),
    )

    live_service = BlockchainService(settings=settings)
    app.dependency_overrides[get_service] = lambda: live_service

    dup_batch_code = f"LIVE-DUP-{uuid4().hex[:8].upper()}"
    test_email = f"test-dup-{uuid4().hex[:6]}@example.com"

    try:
        with SessionLocal() as db_session:
            admin_user = User(
                id=uuid4(),
                name="Duplicate Test Admin",
                email=test_email,
                password_hash=hash_password("Secret123!"),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db_session.add(admin_user)
            db_session.commit()
            db_session.refresh(admin_user)

            batch = Batch(
                id=uuid4(),
                batch_code=dup_batch_code,
                processor_id=admin_user.id,
                status=BatchStatus.ACTIVE,
                created_at=datetime.now(UTC),
            )
            db_session.add(batch)
            db_session.commit()
            db_session.refresh(batch)

            token = create_access_token(subject=admin_user.id, role=admin_user.role)
            headers = {"Authorization": f"Bearer {token}"}

            with TestClient(app) as test_client:
                # 1. First registration should succeed (201)
                res1 = test_client.post(
                    f"/batches/{batch.id}/blockchain-register",
                    headers=headers,
                )
                assert res1.status_code == 201
                body1 = res1.json()
                assert body1["status"] == "CONFIRMED"

                # 2. Second registration for identical batch_code must revert on EVM
                # Solidity HoneyTraceability.sol: require(!batches[batchId].exists, "Batch already exists")
                res2 = test_client.post(
                    f"/batches/{batch.id}/blockchain-register",
                    headers=headers,
                )
                assert res2.status_code == 502
                body2 = res2.json()
                assert "reverted" in body2["detail"].lower() or "failed" in body2["detail"].lower()

                # 3. Verify PostgreSQL audit trail: should have 1 CONFIRMED and 1 FAILED record
                records = db_session.scalars(
                    select(BlockchainRecord)
                    .where(BlockchainRecord.batch_id == batch.id)
                    .order_by(BlockchainRecord.recorded_at.asc())
                ).all()
                assert len(records) == 2
                assert records[0].status == BlockchainStatus.CONFIRMED
                assert records[1].status == BlockchainStatus.FAILED
                assert records[1].transaction_hash is None

                # Clean up created records
                record_ids = [r.id for r in records]
                if record_ids:
                    db_session.execute(
                        delete(AuditEvent).where(
                            AuditEvent.entity_type == "BLOCKCHAIN_RECORD",
                            AuditEvent.entity_id.in_(record_ids),
                        )
                    )
                    db_session.execute(
                        delete(BlockchainRecord).where(
                            BlockchainRecord.id.in_(record_ids)
                        )
                    )
                db_session.execute(delete(Batch).where(Batch.id == batch.id))
                db_session.execute(delete(User).where(User.id == admin_user.id))
                db_session.commit()
    finally:
        app.dependency_overrides.pop(get_service, None)
