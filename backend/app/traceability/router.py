"""FastAPI router for Harvest, Collection Lot, and Processing Batch traceability."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_roles
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.identity import User
from app.traceability.schemas import (
    BatchCreate,
    BatchDetailResponse,
    BatchResponse,
    BatchStatusUpdate,
    CollectionLotAllocationCreate,
    CollectionLotCreate,
    CollectionLotDetailResponse,
    CollectionLotResponse,
    HarvestAllocationCreate,
    HarvestCreate,
    HarvestDetailResponse,
    HarvestResponse,
    HiveAllocationCreate,
)
from app.traceability.service import (
    add_collection_lot_allocation,
    add_harvest_allocation,
    add_hive_allocation,
    create_batch,
    create_collection_lot,
    create_harvest,
    finalize_batch,
    finalize_collection_lot,
    finalize_harvest,
    get_batch_detail,
    get_collection_lot_detail,
    get_harvest_detail,
    list_batches,
    list_collection_lots,
    list_harvests,
    update_batch_status,
)

router = APIRouter(tags=["traceability"])


# ===========================================================================
# Harvest Endpoints
# ===========================================================================

@router.post(
    "/harvests",
    response_model=HarvestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new harvest record",
)
def create_harvest_endpoint(
    payload: HarvestCreate,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.BEEKEEPER)),
) -> HarvestResponse:
    harvest = create_harvest(session, payload, current_user)
    return HarvestResponse.model_validate(harvest)


@router.get(
    "/harvests",
    response_model=list[HarvestResponse],
    status_code=status.HTTP_200_OK,
    summary="List harvests",
)
def list_harvests_endpoint(
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[HarvestResponse]:
    harvests = list_harvests(session, current_user)
    return [HarvestResponse.model_validate(h) for h in harvests]


@router.get(
    "/harvests/{harvest_id}",
    response_model=HarvestDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get harvest details with contributing hives",
)
def get_harvest_endpoint(
    harvest_id: UUID,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HarvestDetailResponse:
    return get_harvest_detail(session, harvest_id, current_user)


@router.post(
    "/harvests/{harvest_id}/hives",
    response_model=HarvestDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Allocate honey from a hive to a harvest",
)
def add_hive_allocation_endpoint(
    harvest_id: UUID,
    payload: HiveAllocationCreate,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.BEEKEEPER)),
) -> HarvestDetailResponse:
    return add_hive_allocation(session, harvest_id, payload, current_user)


@router.post(
    "/harvests/{harvest_id}/finalize",
    response_model=HarvestDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Finalize harvest record",
)
def finalize_harvest_endpoint(
    harvest_id: UUID,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.BEEKEEPER)),
) -> HarvestDetailResponse:
    return finalize_harvest(session, harvest_id, current_user)


# ===========================================================================
# Collection Lot Endpoints
# ===========================================================================

@router.post(
    "/collection-lots",
    response_model=CollectionLotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new collection lot",
)
def create_collection_lot_endpoint(
    payload: CollectionLotCreate,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROCESSOR)),
) -> CollectionLotResponse:
    lot = create_collection_lot(session, payload, current_user)
    return CollectionLotResponse.model_validate(lot)


@router.get(
    "/collection-lots",
    response_model=list[CollectionLotResponse],
    status_code=status.HTTP_200_OK,
    summary="List collection lots",
)
def list_collection_lots_endpoint(
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CollectionLotResponse]:
    lots = list_collection_lots(session, current_user)
    return [CollectionLotResponse.model_validate(lot) for lot in lots]


@router.get(
    "/collection-lots/{lot_id}",
    response_model=CollectionLotDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get collection lot details with contributing harvests",
)
def get_collection_lot_endpoint(
    lot_id: UUID,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CollectionLotDetailResponse:
    return get_collection_lot_detail(session, lot_id, current_user)


@router.post(
    "/collection-lots/{lot_id}/harvests",
    response_model=CollectionLotDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Allocate honey from a harvest to a collection lot",
)
def add_harvest_allocation_endpoint(
    lot_id: UUID,
    payload: HarvestAllocationCreate,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROCESSOR)),
) -> CollectionLotDetailResponse:
    return add_harvest_allocation(session, lot_id, payload, current_user)


@router.post(
    "/collection-lots/{lot_id}/finalize",
    response_model=CollectionLotDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Finalize collection lot",
)
def finalize_collection_lot_endpoint(
    lot_id: UUID,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROCESSOR)),
) -> CollectionLotDetailResponse:
    return finalize_collection_lot(session, lot_id, current_user)


# ===========================================================================
# Processing Batch Endpoints
# ===========================================================================

@router.post(
    "/batches",
    response_model=BatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new processing batch",
)
def create_batch_endpoint(
    payload: BatchCreate,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROCESSOR)),
) -> BatchResponse:
    return create_batch(session, payload, current_user)


@router.get(
    "/batches",
    response_model=list[BatchResponse],
    status_code=status.HTTP_200_OK,
    summary="List processing batches",
)
def list_batches_endpoint(
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BatchResponse]:
    return list_batches(session, current_user)


@router.get(
    "/batches/{batch_id}",
    response_model=BatchDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get processing batch details and full upstream lineage",
)
def get_batch_endpoint(
    batch_id: UUID,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BatchDetailResponse:
    return get_batch_detail(session, batch_id, current_user)


@router.post(
    "/batches/{batch_id}/collection-lots",
    response_model=BatchDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Allocate honey from a collection lot to a processing batch",
)
def add_collection_lot_allocation_endpoint(
    batch_id: UUID,
    payload: CollectionLotAllocationCreate,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROCESSOR)),
) -> BatchDetailResponse:
    return add_collection_lot_allocation(session, batch_id, payload, current_user)


@router.post(
    "/batches/{batch_id}/finalize",
    response_model=BatchDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Finalize processing batch",
)
def finalize_batch_endpoint(
    batch_id: UUID,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROCESSOR)),
) -> BatchDetailResponse:
    return finalize_batch(session, batch_id, current_user)


@router.patch(
    "/batches/{batch_id}/status",
    response_model=BatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Transition batch status (ADMIN only)",
)
def update_batch_status_endpoint(
    batch_id: UUID,
    payload: BatchStatusUpdate,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> BatchResponse:
    return update_batch_status(session, batch_id, payload, current_user)
