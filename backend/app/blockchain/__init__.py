"""Blockchain domain package providing adapter interfaces, cryptographic mapping, and service layer."""

from app.blockchain.abi import HONEY_TRACEABILITY_ABI
from app.blockchain.adapter import (
    BlockchainClient,
    EthereumJsonRpcAdapter,
    MockBlockchainClient,
    UnconfiguredBlockchainClient,
)
from app.blockchain.config import (
    BlockchainClientError,
    BlockchainError,
    BlockchainNotConfiguredError,
    BlockchainSettings,
    BlockchainTransactionError,
)
from app.blockchain.schemas import (
    EMPTY_METADATA_HASH,
    EMPTY_METADATA_HASH_HEX,
    AddEvidencePayload,
    BatchRegistrationPayload,
    BlockchainTxResult,
    EvidenceRecordPayload,
    bytes32_to_hex,
    sha256_hex_to_bytes32,
)
from app.blockchain.service import BlockchainService, get_blockchain_service

__all__ = [
    "AddEvidencePayload",
    "BlockchainClient",
    "BlockchainClientError",
    "BlockchainError",
    "BlockchainNotConfiguredError",
    "BlockchainService",
    "BlockchainSettings",
    "BlockchainTransactionError",
    "BlockchainTxResult",
    "BatchRegistrationPayload",
    "EMPTY_METADATA_HASH",
    "EMPTY_METADATA_HASH_HEX",
    "EthereumJsonRpcAdapter",
    "EvidenceRecordPayload",
    "HONEY_TRACEABILITY_ABI",
    "MockBlockchainClient",
    "UnconfiguredBlockchainClient",
    "bytes32_to_hex",
    "get_blockchain_service",
    "sha256_hex_to_bytes32",
]
