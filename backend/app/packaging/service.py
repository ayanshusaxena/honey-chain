"""Business service layer for Packaging Lot operations."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.audit import AuditEvent
from app.models.enums import BatchStatus, UserRole
from app.models.evidence import PackagingLot
from app.models.identity import User
from app.models.traceability import (
    Batch,
    BatchCollectionLot,
    CollectionLot,
    CollectionLotHarvest,
)
from app.packaging.schemas import (
    PackagingBatchReference,
    PackagingLotCreate,
    PackagingLotDetailResponse,
)


def _calculate_batch_derived_quantity(session: Session, batch_id: UUID) -> Decimal:
    """Calculate total derived quantity in kilograms from collection lots allocated to the batch."""
    total = session.scalar(
        select(func.coalesce(func.sum(BatchCollectionLot.quantity_used_kg), 0)).where(
            BatchCollectionLot.batch_id == batch_id
        )
    )
    if total is None:
        return Decimal("0")
    return Decimal(str(total))


def _calculate_batch_consumed_packaging_kg(session: Session, batch_id: UUID) -> Decimal:
    """Calculate total kilograms already packaged across all packaging lots for the batch using Decimal arithmetic."""
    rows = session.execute(
        select(PackagingLot.quantity, PackagingLot.package_size_grams).where(
            PackagingLot.batch_id == batch_id
        )
    ).all()
    total_kg = Decimal("0")
    for qty, size_grams in rows:
        qty_dec = Decimal(qty)
        size_dec = Decimal(str(size_grams))
        total_kg += (qty_dec * size_dec) / Decimal("1000")
    return total_kg


def _check_batch_read_authorization(batch: Batch, user: User) -> None:
    """Verify user has read authorization for the batch's packaging records."""
    if user.role == UserRole.ADMIN:
        return

    if user.role == UserRole.PROCESSOR:
        if batch.processor_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to view packaging for this batch",
            )
        return

    if user.role == UserRole.BEEKEEPER:
        has_harvest_in_batch = False
        for lot_link in batch.collection_lot_links:
            for harv_link in lot_link.collection_lot.harvest_links:
                if harv_link.harvest.created_by_id == user.id:
                    has_harvest_in_batch = True
                    break
            if has_harvest_in_batch:
                break

        if not has_harvest_in_batch:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to view packaging for this batch",
            )
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient permissions",
    )


def create_packaging_lot(
    session: Session,
    batch_id: UUID,
    payload: PackagingLotCreate,
    current_user: User,
) -> PackagingLot:
    """Create an immutable packaging lot under a finalized, active batch."""
    # Role authorization check
    if current_user.role == UserRole.BEEKEEPER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Beekeepers cannot create packaging lots",
        )

    if current_user.role not in (UserRole.ADMIN, UserRole.PROCESSOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to create packaging lots",
        )

    # Concurrency locking: Lock batch row with FOR UPDATE
    batch = session.scalar(
        select(Batch).where(Batch.id == batch_id).with_for_update()
    )
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )

    # Processor ownership check
    if current_user.role == UserRole.PROCESSOR and batch.processor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Processors can only create packaging for their own batches",
        )

    # Batch prerequisites: Finalized and ACTIVE
    if not batch.is_finalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot create packaging for an unfinalized batch; batch must be finalized first",
        )

    if batch.status != BatchStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot create packaging for batch in {batch.status.value} status; must be ACTIVE",
        )

    # Uniqueness check on package_lot_code
    existing_code = session.scalar(
        select(PackagingLot).where(PackagingLot.package_lot_code == payload.package_lot_code)
    )
    if existing_code is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Packaging lot with code '{payload.package_lot_code}' already exists",
        )

    # Quantity calculation & oversubscription validation using Decimal
    batch_derived_kg = _calculate_batch_derived_quantity(session, batch.id)
    if batch_derived_kg <= Decimal("0"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Batch has zero derived quantity and cannot be packaged",
        )

    existing_consumed_kg = _calculate_batch_consumed_packaging_kg(session, batch.id)
    requested_qty = Decimal(payload.quantity)
    requested_size_grams = Decimal(str(payload.package_size_grams))
    requested_consumed_kg = (requested_qty * requested_size_grams) / Decimal("1000")
    remaining_kg = batch_derived_kg - existing_consumed_kg

    if existing_consumed_kg + requested_consumed_kg > batch_derived_kg:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Packaging consumption ({requested_consumed_kg} kg) exceeds remaining batch quantity ({remaining_kg} kg). "
                f"Total batch: {batch_derived_kg} kg, already packaged: {existing_consumed_kg} kg"
            ),
        )

    # Insert immutable packaging lot
    lot = PackagingLot(
        package_lot_code=payload.package_lot_code,
        batch_id=batch.id,
        quantity=payload.quantity,
        unit=payload.unit,
        package_size_grams=payload.package_size_grams,
    )
    session.add(lot)
    session.flush()

    # Record AuditEvent
    audit_event = AuditEvent(
        event_type="PACKAGING_LOT_CREATED",
        entity_type="PACKAGING_LOT",
        entity_id=lot.id,
        actor_user_id=current_user.id,
        timestamp=datetime.now(UTC),
        metadata_json={
            "batch_id": str(batch.id),
            "package_lot_code": lot.package_lot_code,
            "quantity": lot.quantity,
            "unit": lot.unit.value,
            "package_size_grams": float(lot.package_size_grams),
            "packaged_quantity_kg": lot.packaged_quantity_kg,
        },
    )
    session.add(audit_event)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Packaging lot with code '{payload.package_lot_code}' already exists",
        ) from exc

    session.refresh(lot)
    return lot


def get_batch_packaging_lots(
    session: Session,
    batch_id: UUID,
    current_user: User,
) -> list[PackagingLot]:
    """Retrieve all packaging lots belonging to a batch with lineage RBAC."""
    batch = session.scalar(
        select(Batch)
        .options(
            joinedload(Batch.collection_lot_links)
            .joinedload(BatchCollectionLot.collection_lot)
            .joinedload(CollectionLot.harvest_links)
            .joinedload(CollectionLotHarvest.harvest)
        )
        .where(Batch.id == batch_id)
    )
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )

    _check_batch_read_authorization(batch, current_user)

    lots = session.scalars(
        select(PackagingLot)
        .where(PackagingLot.batch_id == batch_id)
        .order_by(PackagingLot.created_at.asc())
    ).all()

    return list(lots)


def get_packaging_lot_by_id(
    session: Session,
    packaging_lot_id: UUID,
    current_user: User,
) -> PackagingLotDetailResponse:
    """Retrieve a single packaging lot record by ID with batch lineage RBAC."""
    lot = session.scalar(
        select(PackagingLot)
        .options(
            joinedload(PackagingLot.batch)
            .joinedload(Batch.collection_lot_links)
            .joinedload(BatchCollectionLot.collection_lot)
            .joinedload(CollectionLot.harvest_links)
            .joinedload(CollectionLotHarvest.harvest)
        )
        .where(PackagingLot.id == packaging_lot_id)
    )
    if lot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Packaging lot not found",
        )

    _check_batch_read_authorization(lot.batch, current_user)

    batch_derived_kg = _calculate_batch_derived_quantity(session, lot.batch.id)
    batch_ref = PackagingBatchReference(
        id=lot.batch.id,
        batch_code=lot.batch.batch_code,
        processor_id=lot.batch.processor_id,
        status=lot.batch.status,
        is_finalized=lot.batch.is_finalized,
        finalized_at=lot.batch.finalized_at,
        derived_quantity_kg=float(batch_derived_kg),
        created_at=lot.batch.created_at,
        updated_at=lot.batch.updated_at,
    )

    return PackagingLotDetailResponse(
        id=lot.id,
        package_lot_code=lot.package_lot_code,
        batch_id=lot.batch_id,
        quantity=lot.quantity,
        unit=lot.unit,
        package_size_grams=float(lot.package_size_grams),
        packaged_quantity_kg=lot.packaged_quantity_kg,
        created_at=lot.created_at,
        batch=batch_ref,
    )
