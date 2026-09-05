"""Pydantic request and response schemas for hive telemetry."""

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import TelemetryQuality


class TelemetryBase(BaseModel):
    """Shared telemetry measurement fields."""

    device_timestamp: datetime = Field(
        description="Timestamp recorded by the on-hive IoT sensor device.",
    )
    weight_kg: float = Field(
        ge=0,
        description="Gross hive weight in kilograms (must be non-negative).",
    )
    temperature_c: float = Field(
        description="Internal hive or ambient temperature in degrees Celsius.",
    )
    humidity_pct: float = Field(
        ge=0,
        le=100,
        description="Relative humidity percentage (0.0 to 100.0).",
    )
    quality: TelemetryQuality = Field(
        default=TelemetryQuality.VALID,
        description="Data quality indicator (VALID, SUSPECT, INVALID).",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("device_timestamp")
    @classmethod
    def validate_device_timestamp_utc(cls, value: datetime) -> datetime:
        """Ensure device timestamp is explicitly timezone-aware and normalize to UTC."""
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("device_timestamp must include explicit timezone information")
        return value.astimezone(UTC)


class TelemetryCreate(TelemetryBase):
    """Request payload for recording telemetry with an explicit hive_id."""

    hive_id: UUID = Field(
        description="Unique identifier of the target hive.",
    )


class HiveTelemetryCreate(TelemetryBase):
    """Request payload for recording telemetry under /hives/{hive_id}/telemetry."""


class TelemetryResponse(BaseModel):
    """Public representation of an ingested telemetry record."""

    id: UUID
    hive_id: UUID
    device_timestamp: datetime
    received_at: datetime
    weight_kg: float
    temperature_c: float
    humidity_pct: float
    quality: TelemetryQuality

    model_config = ConfigDict(from_attributes=True)
