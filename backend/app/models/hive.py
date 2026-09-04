"""Hive, telemetry, risk, and harvest model definitions."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import HiveStatus, RiskLevel, RiskSource, TelemetryQuality


class Hive(Base):
    __tablename__ = "hives"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    hive_code: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    beekeeper_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    location_region: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[HiveStatus] = mapped_column(
        SAEnum(HiveStatus, name="hive_status"), nullable=False, server_default="ACTIVE"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    beekeeper: Mapped["User"] = relationship(back_populates="hives")
    telemetry_records: Mapped[list["Telemetry"]] = relationship(back_populates="hive")
    risk_events: Mapped[list["RiskEvent"]] = relationship(back_populates="hive")
    harvest_links: Mapped[list["HiveHarvest"]] = relationship(back_populates="hive")


class Telemetry(Base):
    __tablename__ = "telemetry"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    hive_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("hives.id", ondelete="RESTRICT"), nullable=False
    )
    device_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    weight_kg: Mapped[float] = mapped_column(Numeric, nullable=False)
    temperature_c: Mapped[float] = mapped_column(Numeric, nullable=False)
    humidity_pct: Mapped[float] = mapped_column(Numeric, nullable=False)
    quality: Mapped[TelemetryQuality] = mapped_column(
        SAEnum(TelemetryQuality, name="telemetry_quality"), nullable=False
    )

    hive: Mapped["Hive"] = relationship(back_populates="telemetry_records")
    risk_events: Mapped[list["RiskEvent"]] = relationship(back_populates="telemetry")

    __table_args__ = (
        CheckConstraint("weight_kg >= 0", name="ck_telemetry_weight_kg_nonnegative"),
        CheckConstraint("humidity_pct >= 0", name="ck_telemetry_humidity_pct_nonnegative"),
        CheckConstraint("humidity_pct <= 100", name="ck_telemetry_humidity_pct_maximum"),
        Index("ix_telemetry_hive_id_device_timestamp", "hive_id", "device_timestamp"),
    )


class RiskEvent(Base):
    __tablename__ = "risk_events"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    hive_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("hives.id", ondelete="RESTRICT"), nullable=False
    )
    telemetry_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("telemetry.id", ondelete="RESTRICT"), nullable=True
    )
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    risk_score: Mapped[float] = mapped_column(Numeric, nullable=False)
    risk_level: Mapped[RiskLevel] = mapped_column(
        SAEnum(RiskLevel, name="risk_level"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[RiskSource] = mapped_column(SAEnum(RiskSource, name="risk_source"), nullable=False)
    model_name: Mapped[str | None] = mapped_column(String, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    hive: Mapped["Hive"] = relationship(back_populates="risk_events")
    telemetry: Mapped["Telemetry | None"] = relationship(back_populates="risk_events")

    __table_args__ = (
        CheckConstraint("risk_score >= 0 AND risk_score <= 1", name="ck_risk_events_score_range"),
        Index("ix_risk_events_hive_id_evaluated_at", "hive_id", "evaluated_at"),
    )


class Harvest(Base):
    __tablename__ = "harvests"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    harvest_code: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    harvest_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity_kg: Mapped[float] = mapped_column(Numeric, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[UUID] = mapped_column(
        "created_by", PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    is_finalized: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    created_by: Mapped["User"] = relationship(back_populates="created_harvests")
    hive_links: Mapped[list["HiveHarvest"]] = relationship(back_populates="harvest")
    collection_lot_links: Mapped[list["CollectionLotHarvest"]] = relationship(back_populates="harvest")

    __table_args__ = (
        CheckConstraint("quantity_kg > 0", name="ck_harvests_quantity_kg_positive"),
        CheckConstraint(
            "(is_finalized AND finalized_at IS NOT NULL) OR "
            "(NOT is_finalized AND finalized_at IS NULL)",
            name="ck_harvests_finalization_consistency",
        ),
    )


class HiveHarvest(Base):
    __tablename__ = "hive_harvests"

    hive_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("hives.id", ondelete="RESTRICT"), primary_key=True
    )
    harvest_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("harvests.id", ondelete="RESTRICT"), primary_key=True
    )
    quantity_used_kg: Mapped[float] = mapped_column(Numeric, nullable=False)

    hive: Mapped["Hive"] = relationship(back_populates="harvest_links")
    harvest: Mapped["Harvest"] = relationship(back_populates="hive_links")

    __table_args__ = (
        CheckConstraint("quantity_used_kg > 0", name="ck_hive_harvests_quantity_used_kg_positive"),
    )
