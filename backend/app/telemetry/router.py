"""FastAPI HTTP endpoints for telemetry ingestion and retrieval."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.identity import User
from app.telemetry.schemas import (
    HiveTelemetryCreate,
    TelemetryCreate,
    TelemetryResponse,
)
from app.telemetry.service import (
    create_telemetry,
    get_telemetry_by_id,
    list_telemetry,
)

router = APIRouter(tags=["telemetry"])


@router.post(
    "/telemetry",
    response_model=TelemetryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_telemetry_endpoint(
    payload: TelemetryCreate,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.BEEKEEPER))],
    session: Annotated[Session, Depends(get_db)],
) -> TelemetryResponse:
    """Ingest a telemetry record for a hive specified in the payload."""
    telemetry = create_telemetry(session, payload.hive_id, payload, current_user)
    return TelemetryResponse.model_validate(telemetry)


@router.get(
    "/telemetry",
    response_model=list[TelemetryResponse],
    status_code=status.HTTP_200_OK,
)
def list_telemetry_endpoint(
    current_user: Annotated[
        User, Depends(require_roles(UserRole.ADMIN, UserRole.BEEKEEPER, UserRole.PROCESSOR))
    ],
    session: Annotated[Session, Depends(get_db)],
    hive_id: Annotated[UUID | None, Query(description="Filter by specific hive ID")] = None,
) -> list[TelemetryResponse]:
    """Retrieve telemetry records, optionally filtered by hive ID."""
    records = list_telemetry(session, current_user, hive_id=hive_id)
    return [TelemetryResponse.model_validate(item) for item in records]


@router.get(
    "/telemetry/{telemetry_id}",
    response_model=TelemetryResponse,
    status_code=status.HTTP_200_OK,
)
def get_telemetry_endpoint(
    telemetry_id: UUID,
    current_user: Annotated[
        User, Depends(require_roles(UserRole.ADMIN, UserRole.BEEKEEPER, UserRole.PROCESSOR))
    ],
    session: Annotated[Session, Depends(get_db)],
) -> TelemetryResponse:
    """Retrieve a single telemetry record by ID."""
    telemetry = get_telemetry_by_id(session, telemetry_id, current_user)
    return TelemetryResponse.model_validate(telemetry)


@router.post(
    "/hives/{hive_id}/telemetry",
    response_model=TelemetryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_hive_telemetry_endpoint(
    hive_id: UUID,
    payload: HiveTelemetryCreate,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.BEEKEEPER))],
    session: Annotated[Session, Depends(get_db)],
) -> TelemetryResponse:
    """Ingest a telemetry record directly for the hive identified in the path."""
    telemetry = create_telemetry(session, hive_id, payload, current_user)
    return TelemetryResponse.model_validate(telemetry)


@router.get(
    "/hives/{hive_id}/telemetry",
    response_model=list[TelemetryResponse],
    status_code=status.HTTP_200_OK,
)
def list_hive_telemetry_endpoint(
    hive_id: UUID,
    current_user: Annotated[
        User, Depends(require_roles(UserRole.ADMIN, UserRole.BEEKEEPER, UserRole.PROCESSOR))
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[TelemetryResponse]:
    """Retrieve all telemetry records for the specified hive."""
    records = list_telemetry(session, current_user, hive_id=hive_id)
    return [TelemetryResponse.model_validate(item) for item in records]
