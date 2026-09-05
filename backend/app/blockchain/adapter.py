"""Blockchain client protocol, mock client, and RPC adapter boundary."""

from __future__ import annotations

import hashlib
from typing import Any, Protocol, runtime_checkable

from eth_account import Account
from web3 import Web3
from web3.exceptions import ContractCustomError, ContractLogicError, TimeExhausted

from app.blockchain.abi import HONEY_TRACEABILITY_ABI
from app.blockchain.config import (
    BlockchainClientError,
    BlockchainNotConfiguredError,
    BlockchainSettings,
    BlockchainTransactionError,
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
# Production JSON-RPC Adapter
# ===========================================================================

class EthereumJsonRpcAdapter:
    """Production JSON-RPC adapter for HoneyTraceability contract on Ethereum / EVM networks.

    LOCKED CONTRACT INTERFACE:
    - Contract: HoneyTraceability (Ownable)
    - registerBatch(string batchId, bytes32 metadataHash)
    - addEvidence(string batchId, bytes32 evidenceHash)

    MAPPINGS:
    - batch_code -> Solidity string batchId
    - file_hash_sha256 -> exact 32-byte digest -> Solidity bytes32 evidenceHash
    - metadataHash -> bytes32(0)
    """

    def __init__(
        self,
        settings: BlockchainSettings,
        contract_abi: list[dict[str, Any]] | None = None,
        w3: Web3 | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.settings = settings
        self.contract_abi = contract_abi if contract_abi is not None else HONEY_TRACEABILITY_ABI
        self._w3 = w3
        self.timeout_seconds = timeout_seconds

    def is_configured(self) -> bool:
        """Return True only if blockchain is explicitly enabled with required endpoints."""
        return self.settings.is_configured()

    def _get_context(self) -> tuple[Web3, Any, Any, str, int]:
        """Validate configuration, network connectivity, chain ID, and return connection context.

        Returns:
            (w3, contract, account, checksum_contract_address, chain_id)
        """
        if not self.is_configured():
            raise BlockchainNotConfiguredError(
                "Blockchain integration is not configured or disabled."
            )
        if not self.contract_abi:
            raise BlockchainNotConfiguredError(
                "Contract ABI is not configured."
            )
        if not self.settings.private_key:
            raise BlockchainNotConfiguredError(
                "Cannot sign transactions: private key is not configured."
            )

        # 1. Validate contract address
        contract_addr = self.settings.contract_address
        if not Web3.is_address(contract_addr):
            raise BlockchainClientError(
                f"Invalid contract address '{contract_addr}': not a valid Ethereum address."
            )
        checksum_address = Web3.to_checksum_address(contract_addr)

        # 2. Validate signer private key
        try:
            account = Account.from_key(self.settings.private_key.get_secret_value())
        except Exception as exc:
            raise BlockchainClientError(
                f"Invalid private key configured: {exc}"
            ) from exc

        # 3. Connect to Web3 provider
        try:
            w3 = self._w3 or Web3(Web3.HTTPProvider(self.settings.rpc_url))
        except Exception as exc:
            raise BlockchainClientError(
                f"Failed to initialize Web3 provider for '{self.settings.rpc_url}': {exc}"
            ) from exc

        if not w3.is_connected():
            raise BlockchainClientError(
                f"Cannot connect to blockchain RPC node at '{self.settings.rpc_url}'."
            )

        # 4. Validate Chain ID
        try:
            node_chain_id = w3.eth.chain_id
        except Exception as exc:
            raise BlockchainClientError(
                f"Failed to query chain ID from RPC node: {exc}"
            ) from exc

        if self.settings.chain_id is not None and self.settings.chain_id != node_chain_id:
            raise BlockchainClientError(
                f"Configured chain ID ({self.settings.chain_id}) does not match RPC node chain ID ({node_chain_id})."
            )

        # 5. Instantiate contract
        try:
            contract = w3.eth.contract(address=checksum_address, abi=self.contract_abi)
        except Exception as exc:
            raise BlockchainClientError(
                f"Failed to instantiate contract at '{checksum_address}': {exc}"
            ) from exc

        return w3, contract, account, checksum_address, node_chain_id

    def _execute_transaction(
        self,
        func_call: Any,
        checksum_address: str,
        w3: Web3,
        account: Any,
        chain_id: int,
    ) -> BlockchainTxResult:
        """Sign and broadcast a contract transaction and await its receipt."""
        try:
            nonce = w3.eth.get_transaction_count(account.address)
            tx_data = func_call.build_transaction({
                "from": account.address,
                "nonce": nonce,
                "chainId": chain_id,
            })
            if "gas" not in tx_data:
                tx_data["gas"] = 200_000
            if "gasPrice" not in tx_data and "maxFeePerGas" not in tx_data:
                tx_data["gasPrice"] = 1_000_000_000
        except (ContractLogicError, ContractCustomError) as exc:
            raise BlockchainTransactionError(
                f"Contract execution simulated revert: {exc}"
            ) from exc
        except Exception as exc:
            raise BlockchainClientError(
                f"Failed to build transaction: {exc}"
            ) from exc

        # Sign transaction locally using ECDSA secp256k1
        try:
            signed_tx = account.sign_transaction(tx_data)
        except Exception as exc:
            raise BlockchainClientError(
                f"Failed to sign transaction: {exc}"
            ) from exc

        # Broadcast raw transaction
        try:
            tx_hash_bytes = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_hash_hex = (
                tx_hash_bytes.to_0x_hex()
                if hasattr(tx_hash_bytes, "to_0x_hex")
                else f"0x{bytes(tx_hash_bytes).hex()}"
            )
        except Exception as exc:
            raise BlockchainClientError(
                f"Failed to broadcast raw transaction to RPC: {exc}"
            ) from exc

        # Await transaction receipt
        try:
            receipt = w3.eth.wait_for_transaction_receipt(
                tx_hash_bytes,
                timeout=self.timeout_seconds,
            )
        except TimeExhausted as exc:
            raise BlockchainClientError(
                f"Transaction receipt timeout after {self.timeout_seconds}s (tx: {tx_hash_hex}): {exc}"
            ) from exc
        except Exception as exc:
            raise BlockchainClientError(
                f"Error retrieving transaction receipt for '{tx_hash_hex}': {exc}"
            ) from exc

        # Validate on-chain execution status
        status = receipt.get("status")
        if status != 1:
            block_num = receipt.get("blockNumber")
            raise BlockchainTransactionError(
                f"Transaction reverted on-chain with status {status} (tx: {tx_hash_hex}, block: {block_num})."
            )

        return BlockchainTxResult(
            transaction_hash=tx_hash_hex,
            block_number=receipt.get("blockNumber"),
            network=self.settings.network_name,
            contract_address=checksum_address,
            status=BlockchainStatus.CONFIRMED,
        )

    def register_batch(
        self,
        batch_code: str,
        metadata_hash: bytes = EMPTY_METADATA_HASH,
    ) -> BlockchainTxResult:
        if not isinstance(batch_code, str) or not batch_code.strip():
            raise ValueError("batch_code must be a non-empty string.")
        if len(metadata_hash) != 32:
            raise ValueError(f"metadata_hash must be exactly 32 bytes, got {len(metadata_hash)}")

        w3, contract, account, checksum_address, chain_id = self._get_context()

        try:
            func = contract.functions.registerBatch(batch_code, metadata_hash)
        except AttributeError as exc:
            raise BlockchainClientError("Contract does not define 'registerBatch' function.") from exc

        return self._execute_transaction(func, checksum_address, w3, account, chain_id)

    def add_evidence(
        self,
        batch_code: str,
        evidence_hash: bytes,
    ) -> BlockchainTxResult:
        if not isinstance(batch_code, str) or not batch_code.strip():
            raise ValueError("batch_code must be a non-empty string.")
        if len(evidence_hash) != 32:
            raise ValueError(f"evidence_hash must be exactly 32 bytes, got {len(evidence_hash)}")

        w3, contract, account, checksum_address, chain_id = self._get_context()

        try:
            func = contract.functions.addEvidence(batch_code, evidence_hash)
        except AttributeError as exc:
            raise BlockchainClientError("Contract does not define 'addEvidence' function.") from exc

        return self._execute_transaction(func, checksum_address, w3, account, chain_id)

    record_evidence = add_evidence
