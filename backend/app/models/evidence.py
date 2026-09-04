"""Lab evidence, blockchain, packaging, and QR model definitions."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BIGINT, CHAR, CheckConstraint, DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import BlockchainStatus, LabEvidenceStatus, PackagingUnit, QrStatus


class LabEvidence(Base):
    __tablename__ = "lab_evidence"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    batch_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("batches.id", ondelete="RESTRICT"), nullable=False
    )
    certificate_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    test_summary: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    file_hash_sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    status: Mapped[LabEvidenceStatus] = mapped_column(
        SAEnum(LabEvidenceStatus, name="lab_evidence_status"),
        nullable=False,
        server_default="ACTIVE",
    )
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    batch: Mapped["Batch"] = relationship(back_populates="lab_evidence_records")
    blockchain_records: Mapped[list["BlockchainRecord"]] = relationship(back_populates="lab_evidence")


class BlockchainRecord(Base):
    __tablename__ = "blockchain_records"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    batch_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("batches.id", ondelete="RESTRICT"), nullable=False
    )
    lab_evidence_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("lab_evidence.id", ondelete="RESTRICT"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    transaction_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[BlockchainStatus] = mapped_column(
        SAEnum(BlockchainStatus, name="blockchain_status"),
        nullable=False,
        server_default="PENDING",
    )
    network: Mapped[str] = mapped_column(String, nullable=False)
    contract_address: Mapped[str | None] = mapped_column(String, nullable=True)
    block_number: Mapped[int | None] = mapped_column(BIGINT, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    batch: Mapped["Batch"] = relationship(back_populates="blockchain_records")
    lab_evidence: Mapped["LabEvidence | None"] = relationship(back_populates="blockchain_records")


class PackagingLot(Base):
    __tablename__ = "packaging_lots"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    package_lot_code: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    batch_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("batches.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit: Mapped[PackagingUnit] = mapped_column(
        SAEnum(PackagingUnit, name="packaging_unit"), nullable=False
    )
    package_size_grams: Mapped[float] = mapped_column(Numeric, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    batch: Mapped["Batch"] = relationship(back_populates="packaging_lots")
    qr_token: Mapped["QrToken | None"] = relationship(back_populates="packaging_lot", uselist=False)

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_packaging_lots_quantity_positive"),
        CheckConstraint(
            "package_size_grams > 0", name="ck_packaging_lots_package_size_grams_positive"
        ),
    )


class QrToken(Base):
    __tablename__ = "qr_tokens"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    packaging_lot_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("packaging_lots.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    token_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False, unique=True)
    status: Mapped[QrStatus] = mapped_column(
        SAEnum(QrStatus, name="qr_status"), nullable=False, server_default="ACTIVE"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    packaging_lot: Mapped["PackagingLot"] = relationship(back_populates="qr_token")
