"""FastAPI router for Packaging Lot endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_roles
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.identity import User
from app.packaging.schemas import (
    PackagingLotCreate,
    PackagingLotDetailResponse,
    PackagingLotResponse,
)
from app.packaging.service import (
    create_packaging_lot,
    get_batch_packaging_lots,
    get_packaging_lot_by_id,
)

router = APIRouter(tags=["packaging"])


@router.post(
    "/batches/{batch_id}/packaging",
    response_model=PackagingLotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an immutable packaging lot under a finalized batch",
)
def create_packaging_lot_endpoint(
    batch_id: UUID,
    payload: PackagingLotCreate,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROCESSOR)),
) -> PackagingLotResponse:
    """Create a packaging lot consuming from a finalized, active batch."""
    lot = create_packaging_lot(
        session=session,
        batch_id=batch_id,
        payload=payload,
        current_user=current_user,
    )
    return PackagingLotResponse.model_validate(lot)


@router.get(
    "/batches/{batch_id}/packaging",
    response_model=list[PackagingLotResponse],
    status_code=status.HTTP_200_OK,
    summary="Retrieve all packaging lots belonging to a batch",
)
def list_batch_packaging_lots_endpoint(
    batch_id: UUID,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PackagingLotResponse]:
    """Retrieve all packaging lots belonging to a batch, verifying authorization."""
    lots = get_batch_packaging_lots(
        session=session,
        batch_id=batch_id,
        current_user=current_user,
    )
    return [PackagingLotResponse.model_validate(lot) for lot in lots]


@router.get(
    "/packaging/{packaging_lot_id}",
    response_model=PackagingLotDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve a packaging lot by ID",
)
def get_packaging_lot_endpoint(
    packaging_lot_id: UUID,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PackagingLotDetailResponse:
    """Retrieve a single packaging lot and its parent batch reference, verifying authorization."""
    return get_packaging_lot_by_id(
        session=session,
        packaging_lot_id=packaging_lot_id,
        current_user=current_user,
    )
