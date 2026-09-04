"""Collection lot, processing batch, and allocation model definitions."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Index, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import BatchStatus


class CollectionLot(Base):
    __tablename__ = "collection_lots"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    lot_code: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    quantity_kg: Mapped[float] = mapped_column(Numeric, nullable=False)
    is_finalized: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    harvest_links: Mapped[list["CollectionLotHarvest"]] = relationship(
        back_populates="collection_lot"
    )
    batch_links: Mapped[list["BatchCollectionLot"]] = relationship(back_populates="collection_lot")

    __table_args__ = (
        CheckConstraint("quantity_kg > 0", name="ck_collection_lots_quantity_kg_positive"),
        CheckConstraint(
            "(is_finalized AND finalized_at IS NOT NULL) OR "
            "(NOT is_finalized AND finalized_at IS NULL)",
            name="ck_collection_lots_finalization_consistency",
        ),
    )


class CollectionLotHarvest(Base):
    __tablename__ = "collection_lot_harvests"

    collection_lot_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("collection_lots.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    harvest_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("harvests.id", ondelete="RESTRICT"), primary_key=True
    )
    quantity_used_kg: Mapped[float] = mapped_column(Numeric, nullable=False)

    collection_lot: Mapped["CollectionLot"] = relationship(back_populates="harvest_links")
    harvest: Mapped["Harvest"] = relationship(back_populates="collection_lot_links")

    __table_args__ = (
        CheckConstraint(
            "quantity_used_kg > 0", name="ck_collection_lot_harvests_quantity_used_kg_positive"
        ),
        Index("ix_collection_lot_harvests_harvest_id", "harvest_id"),
    )


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    batch_code: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    processor_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[BatchStatus] = mapped_column(
        SAEnum(BatchStatus, name="batch_status"), nullable=False, server_default="ACTIVE"
    )
    is_finalized: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    processor: Mapped["User"] = relationship(back_populates="processed_batches")
    collection_lot_links: Mapped[list["BatchCollectionLot"]] = relationship(back_populates="batch")
    lab_evidence_records: Mapped[list["LabEvidence"]] = relationship(back_populates="batch")
    blockchain_records: Mapped[list["BlockchainRecord"]] = relationship(back_populates="batch")
    packaging_lots: Mapped[list["PackagingLot"]] = relationship(back_populates="batch")

    __table_args__ = (
        CheckConstraint(
            "(is_finalized AND finalized_at IS NOT NULL) OR "
            "(NOT is_finalized AND finalized_at IS NULL)",
            name="ck_batches_finalization_consistency",
        ),
    )


class BatchCollectionLot(Base):
    __tablename__ = "batch_collection_lots"

    batch_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("batches.id", ondelete="RESTRICT"), primary_key=True
    )
    collection_lot_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("collection_lots.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    quantity_used_kg: Mapped[float] = mapped_column(Numeric, nullable=False)

    batch: Mapped["Batch"] = relationship(back_populates="collection_lot_links")
    collection_lot: Mapped["CollectionLot"] = relationship(back_populates="batch_links")

    __table_args__ = (
        CheckConstraint(
            "quantity_used_kg > 0", name="ck_batch_collection_lots_quantity_used_kg_positive"
        ),
        Index("ix_batch_collection_lots_collection_lot_id", "collection_lot_id"),
    )
