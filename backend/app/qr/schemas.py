"""Pydantic schemas and public consumer DTOs for the QR domain."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import (
    BatchStatus,
    BlockchainStatus,
    LabEvidenceStatus,
    PackagingUnit,
    QrStatus,
)


class QrTokenCreateResponse(BaseModel):
    """Response returned upon successful one-time QR token creation."""

    id: UUID
    packaging_lot_id: UUID
    status: QrStatus
    verification_url: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QrTokenMetadataResponse(BaseModel):
    """Internal metadata response for QR tokens without secret tokens or hashes."""

    id: UUID
    packaging_lot_id: UUID
    status: QrStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Public-Safe Consumer DTOs
# ---------------------------------------------------------------------------

class ConsumerBatchInfo(BaseModel):
    """Public representation of batch metadata."""

    batch_code: str
    status: BatchStatus
    is_finalized: bool
    finalized_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConsumerPackagingInfo(BaseModel):
    """Public representation of packaging lot metadata."""

    package_lot_code: str
    quantity: int
    unit: PackagingUnit
    package_size_grams: float
    packaged_quantity_kg: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConsumerProvenanceHarvest(BaseModel):
    """Public representation of harvest and geographic origin."""

    harvest_code: str
    harvest_date: date
    regions: list[str] = []

    model_config = ConfigDict(from_attributes=True)


class ConsumerLabEvidence(BaseModel):
    """Public representation of verified lab certificate."""

    certificate_id: str
    test_summary: str
    file_name: str
    file_hash_sha256: str
    status: LabEvidenceStatus
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConsumerBlockchainRecord(BaseModel):
    """Public representation of on-chain audit reference."""

    event_type: str
    transaction_hash: str | None
    status: BlockchainStatus
    network: str
    contract_address: str | None
    block_number: int | None
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConsumerVerificationResponse(BaseModel):
    """Dedicated public-safe response for consumer verification."""

    verification_status: str  # "VERIFIED", "HOLD", "RECALLED"
    batch: ConsumerBatchInfo
    packaging_lot: ConsumerPackagingInfo
    provenance: list[ConsumerProvenanceHarvest] = []
    lab_evidence: list[ConsumerLabEvidence] = []
    blockchain_records: list[ConsumerBlockchainRecord] = []
    warning: str | None = None
