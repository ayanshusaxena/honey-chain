"""FastAPI router for QR Token and consumer verification endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_roles
from app.core.config import settings
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.identity import User
from app.qr.schemas import (
    ConsumerVerificationResponse,
    QrTokenCreateResponse,
    QrTokenMetadataResponse,
)
from app.qr.service import (
    generate_qr_token,
    get_qr_token_metadata,
    revoke_qr_token,
    verify_consumer_token,
)

router = APIRouter(tags=["qr"])


@router.post(
    "/packaging/{packaging_lot_id}/qr",
    response_model=QrTokenCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a unique single-use QR token for a packaging lot",
)
def create_qr_token_endpoint(
    packaging_lot_id: UUID,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROCESSOR)),
) -> QrTokenCreateResponse:
    """Generate a single-use verification QR token for a packaging lot."""
    return generate_qr_token(
        session=session,
        packaging_lot_id=packaging_lot_id,
        current_user=current_user,
        public_origin=settings.public_origin,
    )


@router.get(
    "/packaging/{packaging_lot_id}/qr",
    response_model=QrTokenMetadataResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve QR token metadata for a packaging lot",
)
def get_qr_token_metadata_endpoint(
    packaging_lot_id: UUID,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QrTokenMetadataResponse:
    """Retrieve metadata of a packaging lot's QR token without exposing secret tokens or hashes."""
    return get_qr_token_metadata(
        session=session,
        packaging_lot_id=packaging_lot_id,
        current_user=current_user,
    )


@router.post(
    "/qr/{qr_id}/revoke",
    response_model=QrTokenMetadataResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke an active QR token",
)
def revoke_qr_token_endpoint(
    qr_id: UUID,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> QrTokenMetadataResponse:
    """Revoke an active QR token. Admin only."""
    return revoke_qr_token(
        session=session,
        qr_id=qr_id,
        current_user=current_user,
    )


@router.get(
    "/verify/{raw_token}",
    response_model=ConsumerVerificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Public consumer verification of a packaging QR token",
)
def verify_consumer_token_endpoint(
    raw_token: str,
    session: Session = Depends(get_db),
) -> ConsumerVerificationResponse:
    """Public, unauthenticated verification endpoint returning a public-safe DTO."""
    return verify_consumer_token(
        session=session,
        raw_token=raw_token,
    )
