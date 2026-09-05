"""Blockchain client protocol, mock client, and RPC adapter boundary."""

from __future__ import annotations

import hashlib
from typing import Any, Protocol, runtime_checkable

from app.blockchain.abi import HONEY_TRACEABILITY_ABI
from app.blockchain.config import (
    BlockchainClientError,
    BlockchainNotConfiguredError,
    BlockchainSettings,
)
from app.blockchain.schemas import (
    EMPTY_METADATA_HASH,
    AddEvidencePayload,
    BatchRegistrationPayload,
    BlockchainTxResult,
    EvidenceRecordPayload,
    bytes32_to_hex,
)
from app.models.enums import BlockchainStatus


@runtime_checkable
class BlockchainClient(Protocol):
    """Abstract protocol defining the required blockchain interactions."""

    def is_configured(self) -> bool:
        """Check if the client has all necessary configuration to connect."""
        ...

    def register_batch(
        self,
        batch_code: str,
        metadata_hash: bytes = EMPTY_METADATA_HASH,
    ) -> BlockchainTxResult:
        """Submit a batch registration transaction to the blockchain contract."""
        ...

    def add_evidence(
        self,
        batch_code: str,
        evidence_hash: bytes,
    ) -> BlockchainTxResult:
        """Submit a lab evidence hash recording transaction to the blockchain contract.

        Maps directly to Solidity: addEvidence(string batchId, bytes32 evidenceHash).
        """
        ...

    def record_evidence(
        self,
        batch_code: str,
        evidence_hash: bytes,
    ) -> BlockchainTxResult:
        """Backward-compatibility alias for add_evidence."""
        ...


# ===========================================================================
# Unconfigured Client
# ===========================================================================

class UnconfiguredBlockchainClient:
    """Client used when blockchain integration is disabled or configuration is missing."""

    def __init__(self, reason: str = "Blockchain integration is not configured or disabled.") -> None:
        self.reason = reason

    def is_configured(self) -> bool:
        return False

    def register_batch(
        self,
        batch_code: str,
        metadata_hash: bytes = EMPTY_METADATA_HASH,
    ) -> BlockchainTxResult:
        raise BlockchainNotConfiguredError(self.reason)

    def add_evidence(
        self,
        batch_code: str,
        evidence_hash: bytes,
    ) -> BlockchainTxResult:
        raise BlockchainNotConfiguredError(self.reason)

    record_evidence = add_evidence


# ===========================================================================
# Mock / Test Client
# ===========================================================================

class MockBlockchainClient:
    """In-memory mock blockchain client for deterministic testing without an external node."""

    def __init__(
        self,
        network_name: str = "mock-chain",
        contract_address: str = "0x5FbDB2315678afecb367f032d93F642f64180aa3",
        simulate_failure: bool = False,
        failure_error_message: str = "Simulated blockchain transaction failure",
    ) -> None:
        self.network_name = network_name
        self.contract_address = contract_address
        self.simulate_failure = simulate_failure
        self.failure_error_message = failure_error_message
        self._tx_counter = 0

        # Recorded calls for verification in tests
        self.registered_batches: list[BatchRegistrationPayload] = []
        self.added_evidences: list[AddEvidencePayload] = []

    @property
    def recorded_evidences(self) -> list[AddEvidencePayload]:
        """Backward-compatibility property alias."""
        return self.added_evidences

    def is_configured(self) -> bool:
        return True

    def _generate_tx_hash(self, action: str, identifier: str) -> str:
        self._tx_counter += 1
        raw = f"{action}:{identifier}:{self._tx_counter}".encode()
        digest = hashlib.sha256(raw).hexdigest()
        return f"0x{digest}"

    def register_batch(
        self,
        batch_code: str,
        metadata_hash: bytes = EMPTY_METADATA_HASH,
    ) -> BlockchainTxResult:
        if self.simulate_failure:
            raise BlockchainClientError(self.failure_error_message)

        payload = BatchRegistrationPayload(
            batch_code=batch_code,
            metadata_hash=metadata_hash,
        )
        self.registered_batches.append(payload)

        tx_hash = self._generate_tx_hash("register_batch", batch_code)
        return BlockchainTxResult(
            transaction_hash=tx_hash,
            block_number=100 + self._tx_counter,
            network=self.network_name,
            contract_address=self.contract_address,
            status=BlockchainStatus.CONFIRMED,
        )

    def add_evidence(
        self,
        batch_code: str,
        evidence_hash: bytes,
    ) -> BlockchainTxResult:
        if self.simulate_failure:
            raise BlockchainClientError(self.failure_error_message)

        payload = AddEvidencePayload(
            batch_code=batch_code,
            evidence_hash=evidence_hash,
        )
        self.added_evidences.append(payload)

        tx_hash = self._generate_tx_hash("add_evidence", batch_code)
        return BlockchainTxResult(
            transaction_hash=tx_hash,
            block_number=100 + self._tx_counter,
            network=self.network_name,
            contract_address=self.contract_address,
            status=BlockchainStatus.CONFIRMED,
        )

    record_evidence = add_evidence


# ===========================================================================
# Production RPC Adapter Boundary (Awaiting Live Deployment & Signer)
# ===========================================================================

class EthereumJsonRpcAdapter:
    """Production adapter boundary configured with verified HoneyTraceability ABI and RPC configuration.

    LOCKED CONTRACT INTERFACE:
    - Contract: HoneyTraceability (Ownable)
    - registerBatch(string batchId, bytes32 metadataHash)
    - addEvidence(string batchId, bytes32 evidenceHash)
    - linkPackaging(string batchId, string packagingRef)
    - updateStatus(string batchId, uint8 newStatus)
    """

    def __init__(self, settings: BlockchainSettings, contract_abi: list[dict[str, Any]] | None = None) -> None:
        self.settings = settings
        self.contract_abi = contract_abi if contract_abi is not None else HONEY_TRACEABILITY_ABI

    def is_configured(self) -> bool:
        return self.settings.is_configured()

    def register_batch(
        self,
        batch_code: str,
        metadata_hash: bytes = EMPTY_METADATA_HASH,
    ) -> BlockchainTxResult:
        if not self.is_configured():
            raise BlockchainNotConfiguredError("Cannot register batch: blockchain RPC or contract address unconfigured.")
        if not self.contract_abi:
            raise BlockchainNotConfiguredError("Contract ABI not configured.")

        # Once contract is deployed and web3/RPC is wired, call:
        # contract.functions.registerBatch(batch_code, metadata_hash).transact()
        raise BlockchainClientError("Live contract interaction is pending deployment to a live network.")

    def add_evidence(
        self,
        batch_code: str,
        evidence_hash: bytes,
    ) -> BlockchainTxResult:
        if not self.is_configured():
            raise BlockchainNotConfiguredError("Cannot add evidence: blockchain RPC or contract address unconfigured.")
        if not self.contract_abi:
            raise BlockchainNotConfiguredError("Contract ABI not configured.")

        # Once contract is deployed and web3/RPC is wired, call:
        # contract.functions.addEvidence(batch_code, evidence_hash).transact()
        raise BlockchainClientError("Live contract interaction is pending deployment to a live network.")

    record_evidence = add_evidence
