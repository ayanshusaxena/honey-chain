"""FastAPI HTTP endpoints for risk evaluation and observation querying."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.identity import User
from app.risk.schemas import RiskEvaluationCreate, RiskEventResponse
from app.risk.service import (
    evaluate_hive_risk,
    get_risk_event_by_id,
    list_hive_risk_events,
)

router = APIRouter(tags=["risk"])


@router.post(
    "/hives/{hive_id}/risk/evaluate",
    response_model=RiskEventResponse,
    status_code=status.HTTP_201_CREATED,
)
@router.post(
    "/hives/{hive_id}/risk",
    response_model=RiskEventResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def evaluate_risk_endpoint(
    hive_id: UUID,
    payload: RiskEvaluationCreate,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.BEEKEEPER))],
    session: Annotated[Session, Depends(get_db)],
) -> RiskEventResponse:
    """Trigger a deterministic prototype risk evaluation for a hive."""
    event = evaluate_hive_risk(session, hive_id, current_user, payload.telemetry_id)
    return RiskEventResponse.model_validate(event)


@router.get(
    "/hives/{hive_id}/risk",
    response_model=list[RiskEventResponse],
    status_code=status.HTTP_200_OK,
)
def list_hive_risk_endpoint(
    hive_id: UUID,
    current_user: Annotated[
        User, Depends(require_roles(UserRole.ADMIN, UserRole.BEEKEEPER, UserRole.PROCESSOR))
    ],
    session: Annotated[Session, Depends(get_db)],
) -> list[RiskEventResponse]:
    """Retrieve risk evaluation events for a specific hive."""
    events = list_hive_risk_events(session, hive_id, current_user)
    return [RiskEventResponse.model_validate(event) for event in events]


@router.get(
    "/risk/{risk_event_id}",
    response_model=RiskEventResponse,
    status_code=status.HTTP_200_OK,
)
def get_risk_event_endpoint(
    risk_event_id: UUID,
    current_user: Annotated[
        User, Depends(require_roles(UserRole.ADMIN, UserRole.BEEKEEPER, UserRole.PROCESSOR))
    ],
    session: Annotated[Session, Depends(get_db)],
) -> RiskEventResponse:
    """Retrieve a single risk event record by ID."""
    event = get_risk_event_by_id(session, risk_event_id, current_user)
    return RiskEventResponse.model_validate(event)
