"""Pydantic schemas for the Admin IoT Simulator control."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SimulatorScenario(str, Enum):
    NORMAL = "NORMAL"
    TEMP_ANOMALY = "TEMP_ANOMALY"
    HUMIDITY_ANOMALY = "HUMIDITY_ANOMALY"
    WEIGHT_DROP = "WEIGHT_DROP"
    COMBINED = "COMBINED"


class SimulatorRunRequest(BaseModel):
    """Admin request to execute a single simulator run."""

    hive_id: UUID = Field(..., description="Target Honey Chain hive UUID")
    scenario: SimulatorScenario = Field(
        default=SimulatorScenario.NORMAL,
        description="Simulator scenario (NORMAL, TEMP_ANOMALY, HUMIDITY_ANOMALY, WEIGHT_DROP, COMBINED)",
    )
    seed: int = Field(default=42, description="Deterministic pseudo-random seed")
    step: int = Field(default=0, ge=0, description="Simulation sequence step")
    ingest: bool = Field(
        default=True,
        description="Whether to ingest generated reading into backend database",
    )

    model_config = ConfigDict(extra="forbid")


class SimulatorRunResponse(BaseModel):
    """Structured response for the admin IoT simulation run."""

    hive_id: UUID
    hive_code: str
    scenario: str
    temperature_c: float
    humidity_pct: float
    weight_kg: float
    quality: str
    device_timestamp: datetime
    telemetry_id: UUID | None = None
    ingestion_status: str
    risk_level: str | None = None
    risk_score: float | None = None
    risk_reasons: list[str] = []
    recommended_action: str | None = None
    simulated: bool = True


class ScenarioInfo(BaseModel):
    id: str
    label: str
    description: str


class ScenarioListResponse(BaseModel):
    scenarios: list[ScenarioInfo]
