"""FastAPI HTTP endpoints for hive management."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles
from app.core.database import get_db
from app.hives.schemas import HiveCreate, HiveResponse, HiveUpdate
from app.hives.service import create_hive, get_hive_by_id, list_hives, update_hive
from app.models.enums import UserRole
from app.models.identity import User

router = APIRouter(prefix="/hives", tags=["hives"])


@router.post(
    "",
    response_model=HiveResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_hive_endpoint(
    payload: HiveCreate,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.BEEKEEPER))],
    session: Annotated[Session, Depends(get_db)],
) -> HiveResponse:
    """Create a new hive for the authenticated beekeeper or assigned by an admin."""
    hive = create_hive(session, payload, current_user)
    return HiveResponse.model_validate(hive)


@router.get(
    "",
    response_model=list[HiveResponse],
    status_code=status.HTTP_200_OK,
)
def list_hives_endpoint(
    current_user: Annotated[
        User, Depends(require_roles(UserRole.ADMIN, UserRole.BEEKEEPER, UserRole.PROCESSOR))
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[HiveResponse]:
    """List hives; beekeepers see own hives while admins and processors see all hives."""
    hives = list_hives(session, current_user)
    return [HiveResponse.model_validate(hive) for hive in hives]


@router.get(
    "/{hive_id}",
    response_model=HiveResponse,
    status_code=status.HTTP_200_OK,
)
def get_hive_endpoint(
    hive_id: UUID,
    current_user: Annotated[
        User, Depends(require_roles(UserRole.ADMIN, UserRole.BEEKEEPER, UserRole.PROCESSOR))
    ],
    session: Annotated[Session, Depends(get_db)],
) -> HiveResponse:
    """View details of a specific hive."""
    hive = get_hive_by_id(session, hive_id, current_user)
    return HiveResponse.model_validate(hive)


@router.patch(
    "/{hive_id}",
    response_model=HiveResponse,
    status_code=status.HTTP_200_OK,
)
def update_hive_endpoint(
    hive_id: UUID,
    payload: HiveUpdate,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.BEEKEEPER))],
    session: Annotated[Session, Depends(get_db)],
) -> HiveResponse:
    """Update hive metadata, operational status, or active workflow flag."""
    hive = update_hive(session, hive_id, payload, current_user)
    return HiveResponse.model_validate(hive)
