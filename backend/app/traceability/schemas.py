"""Pydantic schemas for Honey Chain Harvest, Collection Lot, and Batch Traceability."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import BatchStatus


# ---------------------------------------------------------------------------
# Harvest Schemas
# ---------------------------------------------------------------------------

class HarvestCreate(BaseModel):
    harvest_code: str = Field(..., min_length=3, max_length=50, description="Unique harvest tracking code")
    harvest_date: date = Field(..., description="Date of harvest")
    quantity_kg: float = Field(..., gt=0, description="Total harvested quantity in kilograms")
    notes: str | None = Field(default=None, max_length=1000, description="Optional field notes")
    beekeeper_id: UUID | None = Field(
        default=None,
        description="Target beekeeper ID (Required for ADMIN; automatically set for BEEKEEPER)",
    )

    @field_validator("harvest_code")
    @classmethod
    def validate_code_not_empty(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("harvest_code cannot be empty or whitespace only")
        return clean


class HiveAllocationCreate(BaseModel):
    hive_id: UUID = Field(..., description="ID of the contributing hive")
    quantity_used_kg: float = Field(..., gt=0, description="Quantity of honey contributed in kilograms")


class HiveAllocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hive_id: UUID
    hive_code: str
    location_region: str
    quantity_used_kg: float


class HarvestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    harvest_code: str
    harvest_date: date
    quantity_kg: float
    notes: str | None
    created_by_id: UUID
    is_finalized: bool
    finalized_at: datetime | None
    created_at: datetime
    updated_at: datetime


class HarvestDetailResponse(HarvestResponse):
    allocated_quantity_kg: float
    hives: list[HiveAllocationResponse] = []


# ---------------------------------------------------------------------------
# Collection Lot Schemas
# ---------------------------------------------------------------------------

class CollectionLotCreate(BaseModel):
    lot_code: str = Field(..., min_length=3, max_length=50, description="Unique collection lot tracking code")
    quantity_kg: float = Field(..., gt=0, description="Declared total lot quantity in kilograms")

    @field_validator("lot_code")
    @classmethod
    def validate_code_not_empty(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("lot_code cannot be empty or whitespace only")
        return clean


class HarvestAllocationCreate(BaseModel):
    harvest_id: UUID = Field(..., description="ID of the contributing harvest")
    quantity_used_kg: float = Field(..., gt=0, description="Quantity of honey consumed from harvest in kilograms")


class HarvestAllocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    harvest_id: UUID
    harvest_code: str
    quantity_used_kg: float


class CollectionLotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lot_code: str
    quantity_kg: float
    is_finalized: bool
    finalized_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CollectionLotDetailResponse(CollectionLotResponse):
    allocated_quantity_kg: float
    harvests: list[HarvestAllocationResponse] = []


# ---------------------------------------------------------------------------
# Batch Schemas
# ---------------------------------------------------------------------------

class BatchCreate(BaseModel):
    batch_code: str = Field(..., min_length=3, max_length=50, description="Unique batch tracking code")
    processor_id: UUID | None = Field(
        default=None,
        description="Target processor user ID (Required for ADMIN; automatically set for PROCESSOR)",
    )

    @field_validator("batch_code")
    @classmethod
    def validate_code_not_empty(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("batch_code cannot be empty or whitespace only")
        return clean


class CollectionLotAllocationCreate(BaseModel):
    collection_lot_id: UUID = Field(..., description="ID of the contributing collection lot")
    quantity_used_kg: float = Field(..., gt=0, description="Quantity of honey consumed from lot in kilograms")


class CollectionLotAllocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    collection_lot_id: UUID
    lot_code: str
    quantity_used_kg: float


class BatchStatusUpdate(BaseModel):
    status: BatchStatus = Field(..., description="Target batch status (ACTIVE, HOLD, RECALL)")


class BatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    batch_code: str
    processor_id: UUID
    status: BatchStatus
    is_finalized: bool
    finalized_at: datetime | None
    derived_quantity_kg: float
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Full Upstream Lineage Schemas
# ---------------------------------------------------------------------------

class HiveLineageInBatch(BaseModel):
    hive_id: UUID
    hive_code: str
    location_region: str
    quantity_used_kg: float


class HarvestLineageInBatch(BaseModel):
    harvest_id: UUID
    harvest_code: str
    harvest_date: date
    quantity_used_kg: float
    hives: list[HiveLineageInBatch] = []


class CollectionLotLineageInBatch(BaseModel):
    collection_lot_id: UUID
    lot_code: str
    quantity_used_kg: float
    harvests: list[HarvestLineageInBatch] = []


class BatchDetailResponse(BatchResponse):
    collection_lots: list[CollectionLotLineageInBatch] = []
