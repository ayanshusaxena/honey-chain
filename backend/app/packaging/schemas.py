"""Pydantic schemas for the Packaging Lot domain."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import BatchStatus, PackagingUnit


class PackagingLotCreate(BaseModel):
    """Payload to create a packaging lot under a finalized batch."""

    package_lot_code: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Unique packaging lot tracking code",
    )
    quantity: int = Field(
        ...,
        gt=0,
        description="Number of consumer/package units (must be > 0)",
    )
    unit: PackagingUnit = Field(
        ...,
        description="Unit of measurement (BOTTLES, JARS, PACKS, POUCHES)",
    )
    package_size_grams: float = Field(
        ...,
        gt=0,
        description="Size in grams of one package unit (must be > 0)",
    )
    batch_id: UUID | None = Field(
        default=None,
        description="Optional batch ID in payload; path parameter takes precedence",
    )

    @field_validator("package_lot_code")
    @classmethod
    def validate_code_not_empty(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("package_lot_code cannot be empty or whitespace only")
        return clean


class PackagingLotResponse(BaseModel):
    """Public representation of an immutable packaging lot record."""

    id: UUID
    package_lot_code: str
    batch_id: UUID
    quantity: int
    unit: PackagingUnit
    package_size_grams: float
    packaged_quantity_kg: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def ensure_packaged_quantity_kg(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "packaged_quantity_kg" not in data:
                qty = data.get("quantity")
                size = data.get("package_size_grams")
                if qty is not None and size is not None:
                    qty_dec = Decimal(str(qty))
                    size_dec = Decimal(str(size))
                    data["packaged_quantity_kg"] = float((qty_dec * size_dec) / Decimal("1000"))
        return data


class PackagingBatchReference(BaseModel):
    """Summary reference to the parent batch."""

    id: UUID
    batch_code: str
    processor_id: UUID
    status: BatchStatus
    is_finalized: bool
    finalized_at: datetime | None
    derived_quantity_kg: float | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PackagingLotDetailResponse(PackagingLotResponse):
    """Detailed packaging lot response including parent batch reference."""

    batch: PackagingBatchReference | None = None
