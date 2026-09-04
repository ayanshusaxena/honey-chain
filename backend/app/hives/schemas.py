"""Pydantic request and response schemas for hive management."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import HiveStatus, UserRole


class BeekeeperSummary(BaseModel):
    """Consumer-safe summary of an assigned beekeeper."""

    id: UUID
    name: str
    email: str
    role: UserRole

    model_config = ConfigDict(from_attributes=True)


class HiveCreate(BaseModel):
    """Request payload for creating a new hive."""

    hive_code: str = Field(
        min_length=1,
        max_length=100,
        description="Unique business identifier for the hive.",
    )
    location_region: str = Field(
        min_length=1,
        max_length=255,
        description="General geographic region or zone where the hive is located.",
    )
    beekeeper_id: UUID | None = Field(
        default=None,
        description="Explicit beekeeper user ID (required for ADMIN, forbidden for BEEKEEPER if different).",
    )
    status: HiveStatus = Field(
        default=HiveStatus.ACTIVE,
        description="Initial operational status of the hive.",
    )
    is_active: bool = Field(
        default=True,
        description="Whether the hive is currently active in operational workflows.",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("hive_code")
    @classmethod
    def validate_hive_code(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("hive_code cannot be blank")
        return cleaned

    @field_validator("location_region")
    @classmethod
    def validate_location_region(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("location_region cannot be blank")
        return cleaned


class HiveUpdate(BaseModel):
    """Request payload for modifying an existing hive."""

    location_region: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Updated geographic region.",
    )
    status: HiveStatus | None = Field(
        default=None,
        description="Updated operational status (ACTIVE, INACTIVE, MAINTENANCE).",
    )
    is_active: bool | None = Field(
        default=None,
        description="Updated operational activity flag.",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("location_region")
    @classmethod
    def validate_location_region(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("location_region cannot be blank")
        return cleaned


class HiveResponse(BaseModel):
    """Public representation of a hive record."""

    id: UUID
    hive_code: str
    beekeeper_id: UUID
    location_region: str
    status: HiveStatus
    is_active: bool
    created_at: datetime
    updated_at: datetime
    beekeeper: BeekeeperSummary | None = None

    model_config = ConfigDict(from_attributes=True)
