"""Pydantic request and response schemas for risk evaluation."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RiskLevel, RiskSource


class RiskEvaluationCreate(BaseModel):
    """Request payload for triggering an evaluation for a hive."""

    telemetry_id: UUID | None = Field(
        default=None,
        description="Optional telemetry record ID to evaluate. If omitted, the latest usable telemetry record is used.",
    )

    model_config = ConfigDict(extra="forbid")


class RiskEventResponse(BaseModel):
    """Public representation of an evaluated risk event."""

    id: UUID
    hive_id: UUID
    telemetry_id: UUID | None = None
    evaluated_at: datetime
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_level: RiskLevel
    reason: str
    source: RiskSource
    model_name: str | None = None
    model_version: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
