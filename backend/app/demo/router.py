"""FastAPI HTTP endpoints for the Admin IoT Simulator control."""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles
from app.core.database import get_db
from app.demo.schemas import (
    ScenarioInfo,
    ScenarioListResponse,
    SimulatorRunRequest,
    SimulatorRunResponse,
)
from app.models.enums import UserRole
from app.models.hive import Hive
from app.models.identity import User
from app.telemetry.schemas import TelemetryCreate
from app.telemetry.service import create_telemetry

# Ensure simulator path is available for dynamic generator invocation
SIMULATOR_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "simulator", "honey-chain-ai-iot")
)
if SIMULATOR_DIR not in sys.path:
    sys.path.insert(0, SIMULATOR_DIR)

try:
    from simulator.simulator import generate  # type: ignore
    from ai.risk_engine import evaluate  # type: ignore
except ImportError:
    generate = None  # type: ignore
    evaluate = None  # type: ignore

router = APIRouter(prefix="/demo/simulator", tags=["demo-simulator"])

SCENARIOS_CATALOG = [
    ScenarioInfo(
        id="NORMAL",
        label="NORMAL",
        description="Stable nominal readings within standard hive comfort envelope.",
    ),
    ScenarioInfo(
        id="TEMP_ANOMALY",
        label="TEMP_ANOMALY",
        description="Elevated brood nest temperature condition (heat stress).",
    ),
    ScenarioInfo(
        id="HUMIDITY_ANOMALY",
        label="HUMIDITY_ANOMALY",
        description="Elevated moisture level condition (condensation risk).",
    ),
    ScenarioInfo(
        id="WEIGHT_DROP",
        label="WEIGHT_DROP",
        description="Rapid hive weight decrease indicating potential swarming or honey depletion.",
    ),
    ScenarioInfo(
        id="COMBINED",
        label="COMBINED",
        description="Multiple simultaneous anomalous telemetry signals across temperature, humidity, and weight.",
    ),
]


@router.get(
    "/scenarios",
    response_model=ScenarioListResponse,
    status_code=status.HTTP_200_OK,
    summary="List supported simulator scenarios",
)
def list_scenarios(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
) -> ScenarioListResponse:
    """Return claim-safe supported simulation scenarios for the admin control panel."""
    return ScenarioListResponse(scenarios=SCENARIOS_CATALOG)


@router.post(
    "/run",
    response_model=SimulatorRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute single-shot simulation run for a target hive",
)
def run_simulation(
    payload: SimulatorRunRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    session: Annotated[Session, Depends(get_db)],
) -> SimulatorRunResponse:
    """Execute a deterministic single-shot simulation and ingest into telemetry stream."""
    hive = session.get(Hive, payload.hive_id)
    if hive is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hive with ID {payload.hive_id} not found",
        )

    # 1. Generate telemetry using Python simulator
    if generate is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Simulator module is not available in backend environment",
        )

    sim_hive_target = "HIVE_003" if payload.scenario.value != "NORMAL" else "HIVE_001"
    raw_reading = generate(
        hive_id=sim_hive_target,
        scenario=payload.scenario.value,
        step=payload.step,
        seed=payload.seed,
    )

    device_time = datetime.now(UTC)

    # 2. Local AI evaluation from risk engine
    ai_eval = {}
    if evaluate is not None:
        try:
            ai_eval = evaluate(raw_reading)
        except Exception:
            ai_eval = {}

    # 3. Ingest into telemetry table if requested
    telemetry_record = None
    ingestion_status = "LOCAL_ONLY"
    if payload.ingest:
        telemetry_payload = TelemetryCreate(
            hive_id=hive.id,
            device_timestamp=device_time,
            weight_kg=float(raw_reading["weight_kg"]),
            temperature_c=float(raw_reading["temperature_c"]),
            humidity_pct=float(raw_reading["humidity_pct"]),
            quality="VALID",
        )
        telemetry_record = create_telemetry(session, hive.id, telemetry_payload, current_user)
        ingestion_status = "SUCCESS"

    return SimulatorRunResponse(
        hive_id=hive.id,
        hive_code=hive.hive_code,
        scenario=payload.scenario.value,
        temperature_c=float(raw_reading["temperature_c"]),
        humidity_pct=float(raw_reading["humidity_pct"]),
        weight_kg=float(raw_reading["weight_kg"]),
        quality="VALID",
        device_timestamp=device_time,
        telemetry_id=telemetry_record.id if telemetry_record else None,
        ingestion_status=ingestion_status,
        risk_level=ai_eval.get("risk_level"),
        risk_score=ai_eval.get("risk_score"),
        risk_reasons=ai_eval.get("risk_reasons", []),
        recommended_action=ai_eval.get("recommended_action"),
        simulated=True,
    )
