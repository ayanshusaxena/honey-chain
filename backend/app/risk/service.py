"""Business service layer for deterministic rule-based anomaly and risk evaluation."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import RiskLevel, RiskSource, TelemetryQuality, UserRole
from app.models.hive import Hive, RiskEvent, Telemetry
from app.models.identity import User


def evaluate_telemetry_metrics(
    weight_kg: float,
    temperature_c: float,
    humidity_pct: float,
    quality: TelemetryQuality,
) -> tuple[float, RiskLevel, str]:
    """Evaluate telemetry signals against deterministic prototype demonstration thresholds.

    NOTE: These are prototype anomaly thresholds for MVP demonstration only and do NOT
    represent biological or disease diagnosis standards.
    """
    reasons: list[str] = []
    severity = 0.0

    # Temperature signals (nominal prototype range: 32.0°C to 36.0°C)
    if temperature_c < 28.0 or temperature_c > 40.0:
        severity += 0.40
        reasons.append(f"Critical temperature deviation: {temperature_c:.1f}°C")
    elif temperature_c < 32.0 or temperature_c > 36.0:
        severity += 0.20
        reasons.append(f"Moderate temperature deviation: {temperature_c:.1f}°C")

    # Humidity signals (nominal prototype range: 50.0% to 70.0%)
    if humidity_pct < 30.0 or humidity_pct > 85.0:
        severity += 0.35
        reasons.append(f"Critical humidity deviation: {humidity_pct:.1f}%")
    elif humidity_pct < 40.0 or humidity_pct > 75.0:
        severity += 0.15
        reasons.append(f"Moderate humidity deviation: {humidity_pct:.1f}%")

    # Weight signals (nominal prototype minimum: >= 15.0 kg)
    if weight_kg < 10.0:
        severity += 0.35
        reasons.append(f"Critical low weight reading: {weight_kg:.1f} kg")
    elif weight_kg < 15.0:
        severity += 0.15
        reasons.append(f"Moderate low weight reading: {weight_kg:.1f} kg")

    # Quality signal
    if quality == TelemetryQuality.SUSPECT:
        severity += 0.10
        reasons.append("Telemetry quality flagged as SUSPECT")

    score = min(1.0, max(0.0, round(0.05 + severity, 2)))

    if not reasons:
        score = 0.05
        level = RiskLevel.LOW
        reason_text = "Nominal hive metrics within prototype demonstration thresholds"
    else:
        if score >= 0.70:
            level = RiskLevel.HIGH
        elif score >= 0.40:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW
        reason_text = "; ".join(reasons)

    return score, level, reason_text


def evaluate_hive_risk(
    session: Session,
    hive_id: UUID,
    user: User,
    telemetry_id: UUID | None = None,
) -> RiskEvent:
    """Evaluate and persist a RiskEvent observation for a hive without mutating operational states."""
    hive = session.get(Hive, hive_id)
    if hive is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hive not found",
        )

    if user.role == UserRole.PROCESSOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    if user.role == UserRole.BEEKEEPER and hive.beekeeper_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    if telemetry_id is not None:
        telemetry = session.get(Telemetry, telemetry_id)
        if telemetry is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Telemetry record not found",
            )
        if telemetry.hive_id != hive.id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Telemetry record does not belong to the specified hive",
            )
        if telemetry.quality == TelemetryQuality.INVALID:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot evaluate risk for telemetry with INVALID quality",
            )
    else:
        telemetry = session.scalar(
            select(Telemetry)
            .where(
                Telemetry.hive_id == hive.id,
                Telemetry.quality != TelemetryQuality.INVALID,
            )
            .order_by(Telemetry.device_timestamp.desc())
            .limit(1)
        )
        if telemetry is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No usable telemetry records found for this hive",
            )

    score, level, reason = evaluate_telemetry_metrics(
        weight_kg=float(telemetry.weight_kg),
        temperature_c=float(telemetry.temperature_c),
        humidity_pct=float(telemetry.humidity_pct),
        quality=telemetry.quality,
    )

    risk_event = RiskEvent(
        hive_id=hive.id,
        telemetry_id=telemetry.id,
        evaluated_at=datetime.now(UTC),
        risk_score=score,
        risk_level=level,
        reason=reason,
        source=RiskSource.RULE_ENGINE,
        model_name="prototype-anomaly-rules",
        model_version="1.0.0",
    )
    session.add(risk_event)
    session.commit()
    session.refresh(risk_event)
    return risk_event


def list_hive_risk_events(
    session: Session,
    hive_id: UUID,
    user: User,
) -> Sequence[RiskEvent]:
    """Retrieve risk evaluation events for an authorized hive in reverse-chronological order."""
    hive = session.get(Hive, hive_id)
    if hive is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hive not found",
        )

    if user.role == UserRole.BEEKEEPER and hive.beekeeper_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    query = (
        select(RiskEvent)
        .where(RiskEvent.hive_id == hive_id)
        .order_by(RiskEvent.evaluated_at.desc())
    )
    return session.scalars(query).all()


def get_risk_event_by_id(
    session: Session,
    risk_event_id: UUID,
    user: User,
) -> RiskEvent:
    """Retrieve a single risk event record with ownership validation."""
    event = session.get(RiskEvent, risk_event_id)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Risk event not found",
        )

    hive = session.get(Hive, event.hive_id)
    if user.role == UserRole.BEEKEEPER and (hive is None or hive.beekeeper_id != user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    return event
