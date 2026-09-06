"""Pydantic schemas for the Lab Evidence domain."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import LabEvidenceStatus


class LabEvidenceResponse(BaseModel):
    """Public representation of an immutable lab evidence record."""

    id: UUID
    batch_id: UUID
    certificate_id: str
    test_summary: str
    file_name: str
    file_hash_sha256: str
    status: LabEvidenceStatus
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LabEvidenceVerifyResponse(BaseModel):
    """Verification response for lab evidence artifact and hash."""

    id: UUID
    evidence_id: UUID
    batch_id: UUID
    certificate_id: str
    file_name: str
    file_hash_sha256: str
    computed_hash_sha256: str
    is_hash_verified: bool
    is_verified: bool
    status: LabEvidenceStatus
    claim: str = "The evidence artifact was recorded and its hash is verifiable."
    claim_statement: str = "The evidence artifact was recorded and its hash is verifiable."

    model_config = ConfigDict(from_attributes=True)
