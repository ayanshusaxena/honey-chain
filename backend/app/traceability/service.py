"""Business service layer for Harvest, Collection Lot, and Batch traceability."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.audit import AuditEvent
from app.models.enums import BatchStatus, UserRole
from app.models.hive import Harvest, Hive, HiveHarvest
from app.models.identity import User
from app.models.traceability import Batch, BatchCollectionLot, CollectionLot, CollectionLotHarvest
from app.traceability.schemas import (
    BatchCreate,
    BatchDetailResponse,
    BatchResponse,
    BatchStatusUpdate,
    CollectionLotAllocationCreate,
    CollectionLotCreate,
    CollectionLotDetailResponse,
    CollectionLotLineageInBatch,
    CollectionLotResponse,
    HarvestAllocationCreate,
    HarvestAllocationResponse,
    HarvestCreate,
    HarvestDetailResponse,
    HarvestLineageInBatch,
    HarvestResponse,
    HiveAllocationCreate,
    HiveAllocationResponse,
    HiveLineageInBatch,
)


# ===========================================================================
# Helpers
# ===========================================================================

def _calculate_batch_derived_quantity(session: Session, batch_id: UUID) -> float:
    total = session.scalar(
        select(func.coalesce(func.sum(BatchCollectionLot.quantity_used_kg), 0.0)).where(
            BatchCollectionLot.batch_id == batch_id
        )
    )
    return float(total or 0.0)


# ===========================================================================
# Harvest Services
# ===========================================================================

def create_harvest(session: Session, payload: HarvestCreate, user: User) -> Harvest:
    if user.role == UserRole.PROCESSOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Processors cannot create harvests",
        )

    if user.role == UserRole.BEEKEEPER:
        if payload.beekeeper_id is not None and payload.beekeeper_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Beekeepers cannot create harvests for other users",
            )
        target_beekeeper_id = user.id
    elif user.role == UserRole.ADMIN:
        if payload.beekeeper_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="beekeeper_id is required when an admin creates a harvest",
            )
        target_user = session.get(User, payload.beekeeper_id)
        if target_user is None or not target_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assigned beekeeper not found or inactive",
            )
        if target_user.role != UserRole.BEEKEEPER:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Assigned user must have the BEEKEEPER role",
            )
        target_beekeeper_id = target_user.id
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    existing = session.scalar(select(Harvest).where(Harvest.harvest_code == payload.harvest_code))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Harvest with code '{payload.harvest_code}' already exists",
        )

    harvest = Harvest(
        harvest_code=payload.harvest_code,
        harvest_date=payload.harvest_date,
        quantity_kg=payload.quantity_kg,
        notes=payload.notes,
        created_by_id=target_beekeeper_id,
        is_finalized=False,
        finalized_at=None,
    )
    session.add(harvest)
    session.commit()
    session.refresh(harvest)
    return harvest


def list_harvests(session: Session, user: User) -> list[Harvest]:
    stmt = select(Harvest)
    if user.role == UserRole.BEEKEEPER:
        stmt = stmt.where(Harvest.created_by_id == user.id)
    stmt = stmt.order_by(Harvest.created_at.desc())
    return list(session.scalars(stmt).all())


def get_harvest_detail(session: Session, harvest_id: UUID, user: User) -> HarvestDetailResponse:
    harvest = session.scalar(
        select(Harvest)
        .options(joinedload(Harvest.hive_links).joinedload(HiveHarvest.hive))
        .where(Harvest.id == harvest_id)
    )
    if harvest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Harvest not found",
        )

    if user.role == UserRole.BEEKEEPER and harvest.created_by_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to access this harvest",
        )

    hives_response: list[HiveAllocationResponse] = []
    total_allocated = 0.0
    for link in harvest.hive_links:
        total_allocated += float(link.quantity_used_kg)
        hives_response.append(
            HiveAllocationResponse(
                hive_id=link.hive_id,
                hive_code=link.hive.hive_code,
                location_region=link.hive.location_region,
                quantity_used_kg=float(link.quantity_used_kg),
            )
        )

    return HarvestDetailResponse(
        id=harvest.id,
        harvest_code=harvest.harvest_code,
        harvest_date=harvest.harvest_date,
        quantity_kg=float(harvest.quantity_kg),
        notes=harvest.notes,
        created_by_id=harvest.created_by_id,
        is_finalized=harvest.is_finalized,
        finalized_at=harvest.finalized_at,
        created_at=harvest.created_at,
        updated_at=harvest.updated_at,
        allocated_quantity_kg=round(total_allocated, 4),
        hives=hives_response,
    )


def add_hive_allocation(
    session: Session, harvest_id: UUID, payload: HiveAllocationCreate, user: User
) -> HarvestDetailResponse:
    if user.role == UserRole.PROCESSOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Processors cannot allocate hives to harvests",
        )

    # Concurrency safe row-locking on Harvest
    harvest = session.scalar(
        select(Harvest).where(Harvest.id == harvest_id).with_for_update()
    )
    if harvest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Harvest not found",
        )

    if user.role == UserRole.BEEKEEPER and harvest.created_by_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to modify this harvest",
        )

    if harvest.is_finalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot add allocations to a finalized harvest",
        )

    hive = session.get(Hive, payload.hive_id)
    if hive is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hive not found",
        )

    if not hive.is_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot allocate honey from an inactive hive",
        )

    # Locked Rule: One Harvest belongs to one beekeeper domain. Multiple hives may contribute only when all belong to the same beekeeper.
    if hive.beekeeper_id != harvest.created_by_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cross-beekeeper hive composition is forbidden: hive does not belong to harvest beekeeper domain",
        )

    if user.role == UserRole.BEEKEEPER and hive.beekeeper_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot allocate another beekeeper's hive",
        )

    existing_link = session.get(HiveHarvest, (hive.id, harvest.id))
    if existing_link is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Hive is already linked to this harvest",
        )

    current_allocated = session.scalar(
        select(func.coalesce(func.sum(HiveHarvest.quantity_used_kg), 0.0)).where(
            HiveHarvest.harvest_id == harvest.id
        )
    )
    current_allocated_float = float(current_allocated or 0.0)

    if current_allocated_float + payload.quantity_used_kg > float(harvest.quantity_kg):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Allocation exceeds total harvest quantity of {harvest.quantity_kg} kg",
        )

    link = HiveHarvest(
        hive_id=hive.id,
        harvest_id=harvest.id,
        quantity_used_kg=payload.quantity_used_kg,
    )
    session.add(link)
    session.commit()

    return get_harvest_detail(session, harvest.id, user)


def finalize_harvest(session: Session, harvest_id: UUID, user: User) -> HarvestDetailResponse:
    if user.role == UserRole.PROCESSOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Processors cannot finalize harvests",
        )

    # Concurrency safe row-locking on Harvest
    harvest = session.scalar(
        select(Harvest).where(Harvest.id == harvest_id).with_for_update()
    )
    if harvest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Harvest not found",
        )

    if user.role == UserRole.BEEKEEPER and harvest.created_by_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to finalize this harvest",
        )

    if harvest.is_finalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Harvest is already finalized",
        )

    current_allocated = session.scalar(
        select(func.coalesce(func.sum(HiveHarvest.quantity_used_kg), 0.0)).where(
            HiveHarvest.harvest_id == harvest.id
        )
    )
    current_allocated_float = float(current_allocated or 0.0)

    # Locked Rule: At Harvest finalization, SUM(quantity_used_kg) == Harvest.quantity_kg
    if round(current_allocated_float, 4) != round(float(harvest.quantity_kg), 4):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot finalize harvest: allocated quantity ({current_allocated_float} kg) must exactly equal declared harvest quantity ({harvest.quantity_kg} kg)",
        )

    harvest.is_finalized = True
    harvest.finalized_at = datetime.now(UTC)
    session.commit()

    return get_harvest_detail(session, harvest.id, user)


# ===========================================================================
# Collection Lot Services
# ===========================================================================

def create_collection_lot(session: Session, payload: CollectionLotCreate, user: User) -> CollectionLot:
    if user.role == UserRole.BEEKEEPER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Beekeepers cannot create collection lots",
        )

    existing = session.scalar(
        select(CollectionLot).where(CollectionLot.lot_code == payload.lot_code)
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Collection lot with code '{payload.lot_code}' already exists",
        )

    lot = CollectionLot(
        lot_code=payload.lot_code,
        quantity_kg=payload.quantity_kg,
        is_finalized=False,
        finalized_at=None,
    )
    session.add(lot)
    session.commit()
    session.refresh(lot)
    return lot


def list_collection_lots(session: Session, user: User) -> list[CollectionLot]:
    if user.role in (UserRole.ADMIN, UserRole.PROCESSOR):
        stmt = select(CollectionLot).order_by(CollectionLot.created_at.desc())
        return list(session.scalars(stmt).all())

    # BEEKEEPER: read-only where lineage permits
    stmt = (
        select(CollectionLot)
        .distinct()
        .join(CollectionLot.harvest_links)
        .join(CollectionLotHarvest.harvest)
        .where(Harvest.created_by_id == user.id)
        .order_by(CollectionLot.created_at.desc())
    )
    return list(session.scalars(stmt).all())


def get_collection_lot_detail(
    session: Session, lot_id: UUID, user: User
) -> CollectionLotDetailResponse:
    lot = session.scalar(
        select(CollectionLot)
        .options(joinedload(CollectionLot.harvest_links).joinedload(CollectionLotHarvest.harvest))
        .where(CollectionLot.id == lot_id)
    )
    if lot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection lot not found",
        )

    # Lineage-based authorization for Beekeeper
    if user.role == UserRole.BEEKEEPER:
        user_harvest_exists = any(
            link.harvest.created_by_id == user.id for link in lot.harvest_links
        )
        if not user_harvest_exists:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to view this collection lot",
            )

    harvests_response: list[HarvestAllocationResponse] = []
    total_allocated = 0.0
    for link in lot.harvest_links:
        # Do not expose unrelated beekeeper provenance to a BEEKEEPER
        if user.role == UserRole.BEEKEEPER and link.harvest.created_by_id != user.id:
            continue
        total_allocated += float(link.quantity_used_kg)
        harvests_response.append(
            HarvestAllocationResponse(
                harvest_id=link.harvest_id,
                harvest_code=link.harvest.harvest_code,
                quantity_used_kg=float(link.quantity_used_kg),
            )
        )

    return CollectionLotDetailResponse(
        id=lot.id,
        lot_code=lot.lot_code,
        quantity_kg=float(lot.quantity_kg),
        is_finalized=lot.is_finalized,
        finalized_at=lot.finalized_at,
        created_at=lot.created_at,
        updated_at=lot.updated_at,
        allocated_quantity_kg=round(total_allocated, 4),
        harvests=harvests_response,
    )


def add_harvest_allocation(
    session: Session, lot_id: UUID, payload: HarvestAllocationCreate, user: User
) -> CollectionLotDetailResponse:
    if user.role == UserRole.BEEKEEPER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Beekeepers cannot allocate harvests to collection lots",
        )

    # Consistent locking order: lock CollectionLot first, then Harvest
    lot = session.scalar(
        select(CollectionLot).where(CollectionLot.id == lot_id).with_for_update()
    )
    if lot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection lot not found",
        )

    if lot.is_finalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot add allocations to a finalized collection lot",
        )

    harvest = session.scalar(
        select(Harvest).where(Harvest.id == payload.harvest_id).with_for_update()
    )
    if harvest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Harvest not found",
        )

    existing_link = session.get(CollectionLotHarvest, (lot.id, harvest.id))
    if existing_link is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Harvest is already linked to this collection lot",
        )

    # Rule: For each Harvest: SUM(quantity_used_kg across all linked lots) <= Harvest.quantity_kg
    total_consumed_from_harvest = session.scalar(
        select(func.coalesce(func.sum(CollectionLotHarvest.quantity_used_kg), 0.0)).where(
            CollectionLotHarvest.harvest_id == harvest.id
        )
    )
    total_consumed_float = float(total_consumed_from_harvest or 0.0)
    available_in_harvest = float(harvest.quantity_kg) - total_consumed_float

    if payload.quantity_used_kg > round(available_in_harvest, 4):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Allocation exceeds available source harvest quantity. Available: {available_in_harvest} kg, Requested: {payload.quantity_used_kg} kg",
        )

    # Rule: SUM(quantity_used_kg for this lot) <= CollectionLot.quantity_kg
    current_lot_allocated = session.scalar(
        select(func.coalesce(func.sum(CollectionLotHarvest.quantity_used_kg), 0.0)).where(
            CollectionLotHarvest.collection_lot_id == lot.id
        )
    )
    current_lot_allocated_float = float(current_lot_allocated or 0.0)

    if current_lot_allocated_float + payload.quantity_used_kg > float(lot.quantity_kg):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Allocation exceeds collection lot declared capacity of {lot.quantity_kg} kg",
        )

    link = CollectionLotHarvest(
        collection_lot_id=lot.id,
        harvest_id=harvest.id,
        quantity_used_kg=payload.quantity_used_kg,
    )
    session.add(link)
    session.commit()

    return get_collection_lot_detail(session, lot.id, user)


def finalize_collection_lot(
    session: Session, lot_id: UUID, user: User
) -> CollectionLotDetailResponse:
    if user.role == UserRole.BEEKEEPER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Beekeepers cannot finalize collection lots",
        )

    lot = session.scalar(
        select(CollectionLot).where(CollectionLot.id == lot_id).with_for_update()
    )
    if lot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection lot not found",
        )

    if lot.is_finalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Collection lot is already finalized",
        )

    current_allocated = session.scalar(
        select(func.coalesce(func.sum(CollectionLotHarvest.quantity_used_kg), 0.0)).where(
            CollectionLotHarvest.collection_lot_id == lot.id
        )
    )
    current_allocated_float = float(current_allocated or 0.0)

    # Locked Rule: At Collection Lot finalization, SUM(quantity_used_kg) == CollectionLot.quantity_kg
    if round(current_allocated_float, 4) != round(float(lot.quantity_kg), 4):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot finalize collection lot: allocated quantity ({current_allocated_float} kg) must exactly equal declared lot quantity ({lot.quantity_kg} kg)",
        )

    lot.is_finalized = True
    lot.finalized_at = datetime.now(UTC)
    session.commit()

    return get_collection_lot_detail(session, lot.id, user)


# ===========================================================================
# Batch Services
# ===========================================================================

def create_batch(session: Session, payload: BatchCreate, user: User) -> BatchResponse:
    if user.role == UserRole.BEEKEEPER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Beekeepers cannot create processing batches",
        )

    if user.role == UserRole.PROCESSOR:
        if payload.processor_id is not None and payload.processor_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Processors cannot assign batches to other users",
            )
        target_processor_id = user.id
    elif user.role == UserRole.ADMIN:
        if payload.processor_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="processor_id is required when an admin creates a batch",
            )
        target_user = session.get(User, payload.processor_id)
        if target_user is None or not target_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assigned processor not found or inactive",
            )
        if target_user.role != UserRole.PROCESSOR:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Assigned user must have the PROCESSOR role",
            )
        target_processor_id = target_user.id
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    existing = session.scalar(select(Batch).where(Batch.batch_code == payload.batch_code))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Batch with code '{payload.batch_code}' already exists",
        )

    batch = Batch(
        batch_code=payload.batch_code,
        processor_id=target_processor_id,
        status=BatchStatus.ACTIVE,
        is_finalized=False,
        finalized_at=None,
    )
    session.add(batch)
    session.commit()
    session.refresh(batch)

    return BatchResponse(
        id=batch.id,
        batch_code=batch.batch_code,
        processor_id=batch.processor_id,
        status=batch.status,
        is_finalized=batch.is_finalized,
        finalized_at=batch.finalized_at,
        derived_quantity_kg=0.0,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


def list_batches(session: Session, user: User) -> list[BatchResponse]:
    if user.role in (UserRole.ADMIN, UserRole.PROCESSOR):
        stmt = select(Batch).order_by(Batch.created_at.desc())
        batches = list(session.scalars(stmt).all())
    else:
        # BEEKEEPER: read-only where lineage permits
        stmt = (
            select(Batch)
            .distinct()
            .join(Batch.collection_lot_links)
            .join(BatchCollectionLot.collection_lot)
            .join(CollectionLot.harvest_links)
            .join(CollectionLotHarvest.harvest)
            .where(Harvest.created_by_id == user.id)
            .order_by(Batch.created_at.desc())
        )
        batches = list(session.scalars(stmt).all())

    results: list[BatchResponse] = []
    for b in batches:
        derived_qty = _calculate_batch_derived_quantity(session, b.id)
        results.append(
            BatchResponse(
                id=b.id,
                batch_code=b.batch_code,
                processor_id=b.processor_id,
                status=b.status,
                is_finalized=b.is_finalized,
                finalized_at=b.finalized_at,
                derived_quantity_kg=round(derived_qty, 4),
                created_at=b.created_at,
                updated_at=b.updated_at,
            )
        )
    return results


def get_batch_detail(session: Session, batch_id: UUID, user: User) -> BatchDetailResponse:
    batch = session.scalar(
        select(Batch)
        .options(
            joinedload(Batch.collection_lot_links)
            .joinedload(BatchCollectionLot.collection_lot)
            .joinedload(CollectionLot.harvest_links)
            .joinedload(CollectionLotHarvest.harvest)
            .joinedload(Harvest.hive_links)
            .joinedload(HiveHarvest.hive)
        )
        .where(Batch.id == batch_id)
    )
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )

    # Lineage authorization check for BEEKEEPER
    if user.role == UserRole.BEEKEEPER:
        has_beekeeper_harvest = False
        for lot_link in batch.collection_lot_links:
            for harv_link in lot_link.collection_lot.harvest_links:
                if harv_link.harvest.created_by_id == user.id:
                    has_beekeeper_harvest = True
                    break
            if has_beekeeper_harvest:
                break
        if not has_beekeeper_harvest:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to view this batch",
            )

    collection_lots_response: list[CollectionLotLineageInBatch] = []
    total_batch_qty = 0.0

    for lot_link in batch.collection_lot_links:
        lot = lot_link.collection_lot
        lot_qty = float(lot_link.quantity_used_kg)
        total_batch_qty += lot_qty

        harvests_in_lot: list[HarvestLineageInBatch] = []
        for harv_link in lot.harvest_links:
            harvest = harv_link.harvest
            # Filter out unrelated beekeepers from lineage response
            if user.role == UserRole.BEEKEEPER and harvest.created_by_id != user.id:
                continue

            hives_in_harvest: list[HiveLineageInBatch] = []
            for hive_link in harvest.hive_links:
                hives_in_harvest.append(
                    HiveLineageInBatch(
                        hive_id=hive_link.hive_id,
                        hive_code=hive_link.hive.hive_code,
                        location_region=hive_link.hive.location_region,
                        quantity_used_kg=float(hive_link.quantity_used_kg),
                    )
                )

            harvests_in_lot.append(
                HarvestLineageInBatch(
                    harvest_id=harvest.id,
                    harvest_code=harvest.harvest_code,
                    harvest_date=harvest.harvest_date,
                    quantity_used_kg=float(harv_link.quantity_used_kg),
                    hives=hives_in_harvest,
                )
            )

        if user.role == UserRole.BEEKEEPER and not harvests_in_lot:
            # If this lot had no harvests belonging to this beekeeper, skip lot presentation
            continue

        collection_lots_response.append(
            CollectionLotLineageInBatch(
                collection_lot_id=lot.id,
                lot_code=lot.lot_code,
                quantity_used_kg=lot_qty,
                harvests=harvests_in_lot,
            )
        )

    return BatchDetailResponse(
        id=batch.id,
        batch_code=batch.batch_code,
        processor_id=batch.processor_id,
        status=batch.status,
        is_finalized=batch.is_finalized,
        finalized_at=batch.finalized_at,
        derived_quantity_kg=round(total_batch_qty, 4),
        created_at=batch.created_at,
        updated_at=batch.updated_at,
        collection_lots=collection_lots_response,
    )


def add_collection_lot_allocation(
    session: Session, batch_id: UUID, payload: CollectionLotAllocationCreate, user: User
) -> BatchDetailResponse:
    if user.role == UserRole.BEEKEEPER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Beekeepers cannot allocate collection lots to batches",
        )

    # Consistent locking order: lock Batch first, then CollectionLot
    batch = session.scalar(
        select(Batch).where(Batch.id == batch_id).with_for_update()
    )
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )

    if batch.is_finalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot add allocations to a finalized batch",
        )

    if batch.status != BatchStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot add allocations to a batch that is not ACTIVE",
        )

    lot = session.scalar(
        select(CollectionLot).where(CollectionLot.id == payload.collection_lot_id).with_for_update()
    )
    if lot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection lot not found",
        )

    existing_link = session.get(BatchCollectionLot, (batch.id, lot.id))
    if existing_link is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Collection lot is already linked to this batch",
        )

    # Rule: For each Collection Lot: SUM(quantity_used_kg across all linked batches) <= CollectionLot.quantity_kg
    total_consumed_from_lot = session.scalar(
        select(func.coalesce(func.sum(BatchCollectionLot.quantity_used_kg), 0.0)).where(
            BatchCollectionLot.collection_lot_id == lot.id
        )
    )
    total_consumed_float = float(total_consumed_from_lot or 0.0)
    available_in_lot = float(lot.quantity_kg) - total_consumed_float

    if payload.quantity_used_kg > round(available_in_lot, 4):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Allocation exceeds available collection lot quantity. Available: {available_in_lot} kg, Requested: {payload.quantity_used_kg} kg",
        )

    link = BatchCollectionLot(
        batch_id=batch.id,
        collection_lot_id=lot.id,
        quantity_used_kg=payload.quantity_used_kg,
    )
    session.add(link)
    session.commit()

    return get_batch_detail(session, batch.id, user)


def finalize_batch(session: Session, batch_id: UUID, user: User) -> BatchDetailResponse:
    if user.role == UserRole.BEEKEEPER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Beekeepers cannot finalize processing batches",
        )

    batch = session.scalar(
        select(Batch).where(Batch.id == batch_id).with_for_update()
    )
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )

    if batch.is_finalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Batch is already finalized",
        )

    if batch.status != BatchStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot finalize a batch that is not ACTIVE",
        )

    # Locked Rule: Batch finalization requires at least one valid BatchCollectionLot allocation
    alloc_count = session.scalar(
        select(func.count())
        .select_from(BatchCollectionLot)
        .where(BatchCollectionLot.batch_id == batch.id)
    )
    if not alloc_count or alloc_count == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot finalize batch: at least one Collection Lot allocation is required",
        )

    batch.is_finalized = True
    batch.finalized_at = datetime.now(UTC)
    session.commit()

    return get_batch_detail(session, batch.id, user)


def update_batch_status(
    session: Session, batch_id: UUID, payload: BatchStatusUpdate, user: User
) -> BatchResponse:
    # Locked Rule: Only ADMIN may change Batch status.
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update batch status",
        )

    batch = session.scalar(
        select(Batch).where(Batch.id == batch_id).with_for_update()
    )
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )

    # Locked Rule: Unfinalized Batch cannot enter HOLD or RECALL
    if not batch.is_finalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unfinalized batches cannot transition status",
        )

    # Idempotent if status is already target
    if batch.status == payload.status:
        derived_qty = _calculate_batch_derived_quantity(session, batch.id)
        return BatchResponse(
            id=batch.id,
            batch_code=batch.batch_code,
            processor_id=batch.processor_id,
            status=batch.status,
            is_finalized=batch.is_finalized,
            finalized_at=batch.finalized_at,
            derived_quantity_kg=round(derived_qty, 4),
            created_at=batch.created_at,
            updated_at=batch.updated_at,
        )

    # State Machine Validation:
    # ACTIVE -> HOLD, ACTIVE -> RECALL
    # HOLD -> ACTIVE
    # RECALL is terminal
    # Reject: HOLD -> RECALL, RECALL -> ACTIVE, RECALL -> HOLD
    current_status = batch.status
    target_status = payload.status

    if current_status == BatchStatus.RECALL:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Illegal status transition: RECALL is a terminal status and cannot be changed",
        )

    if current_status == BatchStatus.HOLD and target_status == BatchStatus.RECALL:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Illegal status transition: HOLD cannot transition directly to RECALL (must return to ACTIVE first)",
        )

    if current_status == BatchStatus.ACTIVE and target_status not in (BatchStatus.HOLD, BatchStatus.RECALL):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Illegal status transition from ACTIVE to {target_status.value}",
        )

    if current_status == BatchStatus.HOLD and target_status != BatchStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Illegal status transition from HOLD to {target_status.value}",
        )

    # Record Audit Event
    audit_event = AuditEvent(
        event_type="BATCH_STATUS_TRANSITION",
        entity_type="BATCH",
        entity_id=batch.id,
        actor_user_id=user.id,
        timestamp=datetime.now(UTC),
        metadata_json={
            "from_status": current_status.value,
            "to_status": target_status.value,
            "batch_code": batch.batch_code,
        },
    )
    session.add(audit_event)

    batch.status = target_status
    session.commit()
    session.refresh(batch)

    derived_qty = _calculate_batch_derived_quantity(session, batch.id)
    return BatchResponse(
        id=batch.id,
        batch_code=batch.batch_code,
        processor_id=batch.processor_id,
        status=batch.status,
        is_finalized=batch.is_finalized,
        finalized_at=batch.finalized_at,
        derived_quantity_kg=round(derived_qty, 4),
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )
