"""Service layer orchestrating blockchain adapter operations and database record persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.blockchain.adapter import (
    BlockchainClient,
    MockBlockchainClient,
    UnconfiguredBlockchainClient,
)
from app.blockchain.config import (
    BlockchainClientError,
    BlockchainError,
    BlockchainNotConfiguredError,
    BlockchainSettings,
)
from app.blockchain.schemas import (
    EMPTY_METADATA_HASH,
    sha256_hex_to_bytes32,
)
from app.models.audit import AuditEvent
from app.models.enums import BlockchainStatus
from app.models.evidence import BlockchainRecord, LabEvidence
from app.models.traceability import Batch


class BlockchainService:
    """Service orchestrating blockchain adapter calls, hash mappings, and PostgreSQL audit records."""

    def __init__(
        self,
        client: BlockchainClient | None = None,
        settings: BlockchainSettings | None = None,
    ) -> None:
        self.settings = settings or BlockchainSettings()
        if client is not None:
            self.client = client
        elif self.settings.is_configured():
            # Ready to switch to EthereumJsonRpcAdapter once ABI is provided
            self.client = MockBlockchainClient(
                network_name=self.settings.network_name,
                contract_address=self.settings.contract_address or "0x0000000000000000000000000000000000000000",
            )
        else:
            self.client = UnconfiguredBlockchainClient()

    def register_batch_on_chain(
        self,
        session: Session,
        batch_id: UUID,
    ) -> BlockchainRecord:
        """Register a processing batch on the blockchain contract.

        LOCKED RULES:
        - Blockchain identity MUST be Batch.batch_code (never Batch.id UUID).
        - metadataHash MUST be bytes32(0).
        """
        batch = session.scalar(select(Batch).where(Batch.id == batch_id))
        if batch is None:
            raise ValueError(f"Batch with ID '{batch_id}' not found.")

        # Fail closed if blockchain client is unconfigured
        if not self.client.is_configured():
            raise BlockchainNotConfiguredError(
                "Blockchain integration is not configured or disabled."
            )

        try:
            tx_result = self.client.register_batch(
                batch_code=batch.batch_code,
                metadata_hash=EMPTY_METADATA_HASH,
            )
        except BlockchainClientError as exc:
            # Record failed transaction attempt in PostgreSQL audit table
            failed_record = BlockchainRecord(
                id=uuid4(),
                batch_id=batch.id,
                lab_evidence_id=None,
                event_type="BATCH_REGISTERED",
                transaction_hash=None,
                status=BlockchainStatus.FAILED,
                network=self.settings.network_name,
                contract_address=self.settings.contract_address,
                block_number=None,
                recorded_at=datetime.now(UTC),
            )
            session.add(failed_record)
            try:
                session.commit()
                session.refresh(failed_record)
            except Exception:
                session.rollback()
            raise BlockchainClientError(
                f"Failed to register batch '{batch.batch_code}' on-chain: {exc}"
            ) from exc

        record = BlockchainRecord(
            id=uuid4(),
            batch_id=batch.id,
            lab_evidence_id=None,
            event_type="BATCH_REGISTERED",
            transaction_hash=tx_result.transaction_hash,
            status=tx_result.status,
            network=tx_result.network,
            contract_address=tx_result.contract_address,
            block_number=tx_result.block_number,
            recorded_at=datetime.now(UTC),
        )
        session.add(record)

        audit_event = AuditEvent(
            event_type="BLOCKCHAIN_BATCH_REGISTERED",
            entity_type="BLOCKCHAIN_RECORD",
            entity_id=record.id,
            actor_user_id=batch.processor_id,
            timestamp=datetime.now(UTC),
            metadata_json={
                "batch_id": str(batch.id),
                "batch_code": batch.batch_code,
                "transaction_hash": tx_result.transaction_hash,
                "network": tx_result.network,
            },
        )
        session.add(audit_event)

        try:
            session.commit()
            session.refresh(record)
        except Exception:
            session.rollback()
            raise
        return record

    def add_evidence_on_chain(
        self,
        session: Session,
        evidence_id: UUID,
    ) -> BlockchainRecord:
        """Record a verified LabEvidence file hash on the blockchain contract (addEvidence).

        LOCKED RULES:
        - Must consume existing LabEvidence.file_hash_sha256 (do not recompute from file).
        - Must preserve the exact 32-byte digest (no second hash, no Keccak256).
        - Must link to the associated batch using Batch.batch_code.
        - Maps directly to Solidity HoneyTraceability.addEvidence(batchId, evidenceHash).
        """
        evidence = session.scalar(
            select(LabEvidence).where(LabEvidence.id == evidence_id)
        )
        if evidence is None:
            raise ValueError(f"Lab evidence with ID '{evidence_id}' not found.")

        batch = session.scalar(select(Batch).where(Batch.id == evidence.batch_id))
        if batch is None:
            raise ValueError(f"Batch with ID '{evidence.batch_id}' not found.")

        # Fail closed if blockchain client is unconfigured
        if not self.client.is_configured():
            raise BlockchainNotConfiguredError(
                "Blockchain integration is not configured or disabled."
            )

        # Convert 64-char SHA-256 hex string directly into 32-byte digest
        # NO REHASHING — preserves exact bytes
        evidence_bytes32 = sha256_hex_to_bytes32(evidence.file_hash_sha256)

        try:
            tx_result = self.client.add_evidence(
                batch_code=batch.batch_code,
                evidence_hash=evidence_bytes32,
            )
        except BlockchainClientError as exc:
            failed_record = BlockchainRecord(
                id=uuid4(),
                batch_id=batch.id,
                lab_evidence_id=evidence.id,
                event_type="LAB_EVIDENCE_RECORDED",
                transaction_hash=None,
                status=BlockchainStatus.FAILED,
                network=self.settings.network_name,
                contract_address=self.settings.contract_address,
                block_number=None,
                recorded_at=datetime.now(UTC),
            )
            session.add(failed_record)
            try:
                session.commit()
                session.refresh(failed_record)
            except Exception:
                session.rollback()
            raise BlockchainClientError(
                f"Failed to record evidence '{evidence.certificate_id}' on-chain: {exc}"
            ) from exc

        record = BlockchainRecord(
            id=uuid4(),
            batch_id=batch.id,
            lab_evidence_id=evidence.id,
            event_type="LAB_EVIDENCE_RECORDED",
            transaction_hash=tx_result.transaction_hash,
            status=tx_result.status,
            network=tx_result.network,
            contract_address=tx_result.contract_address,
            block_number=tx_result.block_number,
            recorded_at=datetime.now(UTC),
        )
        session.add(record)

        audit_event = AuditEvent(
            event_type="BLOCKCHAIN_EVIDENCE_RECORDED",
            entity_type="BLOCKCHAIN_RECORD",
            entity_id=record.id,
            actor_user_id=batch.processor_id,
            timestamp=datetime.now(UTC),
            metadata_json={
                "batch_id": str(batch.id),
                "batch_code": batch.batch_code,
                "evidence_id": str(evidence.id),
                "certificate_id": evidence.certificate_id,
                "file_hash_sha256": evidence.file_hash_sha256,
                "transaction_hash": tx_result.transaction_hash,
                "network": tx_result.network,
            },
        )
        session.add(audit_event)

        try:
            session.commit()
            session.refresh(record)
        except Exception:
            session.rollback()
            raise
        return record

    # Backward-compatibility alias
    record_evidence_on_chain = add_evidence_on_chain

    def get_batch_blockchain_records(
        self,
        session: Session,
        batch_id: UUID,
    ) -> list[BlockchainRecord]:
        """Retrieve all blockchain audit records recorded for a given batch."""
        records = session.scalars(
            select(BlockchainRecord)
            .where(BlockchainRecord.batch_id == batch_id)
            .order_by(BlockchainRecord.recorded_at.desc())
        ).all()
        return list(records)


def get_blockchain_service(
    client: BlockchainClient | None = None,
    settings: BlockchainSettings | None = None,
) -> BlockchainService:
    """Factory helper providing the BlockchainService instance."""
    return BlockchainService(client=client, settings=settings)
