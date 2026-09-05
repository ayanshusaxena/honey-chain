"""Business service layer for append-only telemetry ingestion and retrieval."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from app.models.hive import Hive, Telemetry
from app.models.identity import User
from app.telemetry.schemas import TelemetryBase


def create_telemetry(
    session: Session,
    hive_id: UUID,
    payload: TelemetryBase,
    user: User,
) -> Telemetry:
    """Ingest a single append-only telemetry record with ownership verification."""
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

    received_at = datetime.now(UTC)

    telemetry = Telemetry(
        hive_id=hive.id,
        device_timestamp=payload.device_timestamp,
        received_at=received_at,
        weight_kg=payload.weight_kg,
        temperature_c=payload.temperature_c,
        humidity_pct=payload.humidity_pct,
        quality=payload.quality,
    )
    session.add(telemetry)
    session.commit()
    session.refresh(telemetry)
    return telemetry


def list_telemetry(
    session: Session,
    user: User,
    hive_id: UUID | None = None,
) -> Sequence[Telemetry]:
    """Retrieve telemetry records enforcing role visibility and ownership boundaries."""
    if hive_id is not None:
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
            select(Telemetry)
            .where(Telemetry.hive_id == hive_id)
            .order_by(Telemetry.device_timestamp.desc())
        )
    else:
        query = select(Telemetry).order_by(Telemetry.device_timestamp.desc())
        if user.role == UserRole.BEEKEEPER:
            query = query.join(Hive, Telemetry.hive_id == Hive.id).where(
                Hive.beekeeper_id == user.id
            )

    return session.scalars(query).all()


def get_telemetry_by_id(
    session: Session,
    telemetry_id: UUID,
    user: User,
) -> Telemetry:
    """Retrieve a single telemetry record with ownership validation."""
    telemetry = session.get(Telemetry, telemetry_id)
    if telemetry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Telemetry record not found",
        )

    hive = session.get(Hive, telemetry.hive_id)
    if user.role == UserRole.BEEKEEPER and (hive is None or hive.beekeeper_id != user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    return telemetry
