"""Schemas, payloads, and cryptographic conversion utilities for blockchain integration."""

from __future__ import annotations

from datetime import datetime
import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import BlockchainStatus

# Canonical Solidity bytes32(0)
EMPTY_METADATA_HASH: bytes = b"\x00" * 32
EMPTY_METADATA_HASH_HEX: str = "0x" + "00" * 32

_HEX64_REGEX = re.compile(r"^(?:0x)?([a-fA-F0-9]{64})$")


def sha256_hex_to_bytes32(hex_str: str) -> bytes:
    """Convert a 64-character SHA-256 hexadecimal string into its exact 32-byte digest.

    LOCKED ARCHITECTURE REQUIREMENT:
    - Must preserve the exact 32-byte digest represented by the 64-char SHA-256 hex.
    - Zero rehashing (do not hash the hex string or rehash the digest).
    - Do not use Keccak256 for LabEvidence.
    """
    if not isinstance(hex_str, str):
        raise ValueError(f"Expected hex string, got {type(hex_str).__name__}")

    clean = hex_str.strip()
    match = _HEX64_REGEX.match(clean)
    if not match:
        raise ValueError(
            f"Invalid SHA-256 hex string: expected exactly 64 hexadecimal characters, got {len(clean)}"
        )

    raw_hex = match.group(1)
    raw_bytes = bytes.fromhex(raw_hex)
    if len(raw_bytes) != 32:
        raise ValueError(f"Expected exactly 32 bytes after hex conversion, got {len(raw_bytes)}")

    return raw_bytes


def bytes32_to_hex(b: bytes) -> str:
    """Convert a 32-byte digest into a standard 0x-prefixed 64-character lowercase hex string."""
    if not isinstance(b, (bytes, bytearray)):
        raise ValueError(f"Expected bytes, got {type(b).__name__}")
    if len(b) != 32:
        raise ValueError(f"Expected exactly 32 bytes, got {len(b)}")
    return f"0x{b.hex().lower()}"


class BlockchainTxResult(BaseModel):
    """Result of an executed or simulated on-chain transaction."""

    transaction_hash: str
    block_number: int | None = None
    network: str
    contract_address: str | None = None
    status: BlockchainStatus = BlockchainStatus.CONFIRMED

    model_config = ConfigDict(from_attributes=True)


class BatchRegistrationPayload(BaseModel):
    """Payload representing batch registration parameters for the blockchain contract."""

    batch_code: str = Field(..., min_length=1, description="Unique batch code mapped to Solidity batchId")
    metadata_hash: bytes = Field(default=EMPTY_METADATA_HASH, description="Solidity metadataHash, fixed to bytes32(0)")

    @field_validator("metadata_hash")
    @classmethod
    def validate_metadata_hash(cls, v: bytes) -> bytes:
        if len(v) != 32:
            raise ValueError(f"metadata_hash must be exactly 32 bytes, got {len(v)}")
        return v


class AddEvidencePayload(BaseModel):
    """Payload representing evidence addition parameters for the blockchain contract (addEvidence)."""

    batch_code: str = Field(..., min_length=1, description="Unique batch code of the associated batch")
    evidence_hash: bytes = Field(..., description="Exact 32-byte SHA-256 digest of the certificate file")

    @field_validator("evidence_hash")
    @classmethod
    def validate_evidence_hash(cls, v: bytes) -> bytes:
        if len(v) != 32:
            raise ValueError(f"evidence_hash must be exactly 32 bytes, got {len(v)}")
        return v


# Backward compatibility alias
EvidenceRecordPayload = AddEvidencePayload


class BlockchainRecordResponse(BaseModel):
    """Pydantic response schema for a persisted BlockchainRecord."""

    id: UUID
    batch_id: UUID
    lab_evidence_id: UUID | None = None
    event_type: str
    transaction_hash: str | None = None
    status: BlockchainStatus
    network: str
    contract_address: str | None = None
    block_number: int | None = None
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)
