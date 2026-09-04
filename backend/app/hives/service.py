"""Business service layer for hive operations."""

from collections.abc import Sequence
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.hives.schemas import HiveCreate, HiveUpdate
from app.models.enums import UserRole
from app.models.hive import Hive
from app.models.identity import User


def create_hive(session: Session, payload: HiveCreate, user: User) -> Hive:
    """Create a new hive, enforcing role-based ownership assignment and code uniqueness."""
    if user.role == UserRole.BEEKEEPER:
        if payload.beekeeper_id is not None and payload.beekeeper_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot assign hive to another user",
            )
        beekeeper_id = user.id
    elif user.role == UserRole.ADMIN:
        if payload.beekeeper_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="beekeeper_id is required when creating a hive as an administrator",
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
        beekeeper_id = target_user.id
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    # Check for duplicate hive_code
    existing = session.scalar(
        select(Hive).where(func.lower(Hive.hive_code) == func.lower(payload.hive_code))
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Hive with code '{payload.hive_code}' already exists",
        )

    hive = Hive(
        hive_code=payload.hive_code,
        beekeeper_id=beekeeper_id,
        location_region=payload.location_region,
        status=payload.status,
        is_active=payload.is_active,
    )
    session.add(hive)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Hive with code '{payload.hive_code}' already exists",
        ) from exc

    session.refresh(hive)
    return hive


def list_hives(session: Session, user: User) -> Sequence[Hive]:
    """List hives based on user role: BEEKEEPER sees own, ADMIN and PROCESSOR see all."""
    query = select(Hive).options(joinedload(Hive.beekeeper)).order_by(Hive.created_at.desc())
    if user.role == UserRole.BEEKEEPER:
        query = query.where(Hive.beekeeper_id == user.id)
    return session.scalars(query).all()


def get_hive_by_id(session: Session, hive_id: UUID, user: User) -> Hive:
    """Retrieve a single hive by ID with role-based access validation."""
    hive = session.scalar(
        select(Hive).options(joinedload(Hive.beekeeper)).where(Hive.id == hive_id)
    )
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

    return hive


def update_hive(
    session: Session,
    hive_id: UUID,
    payload: HiveUpdate,
    user: User,
) -> Hive:
    """Update mutable hive fields (location_region, status, is_active) with ownership validation."""
    hive = session.scalar(
        select(Hive).options(joinedload(Hive.beekeeper)).where(Hive.id == hive_id)
    )
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

    if user.role not in (UserRole.ADMIN, UserRole.BEEKEEPER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    if payload.location_region is not None:
        hive.location_region = payload.location_region

    if payload.status is not None:
        hive.status = payload.status

    if payload.is_active is not None:
        hive.is_active = payload.is_active

    session.commit()
    session.refresh(hive)
    return hive
