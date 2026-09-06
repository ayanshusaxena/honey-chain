"""Business service layer for QR Token lifecycle and consumer verification."""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.audit import AuditEvent
from app.models.enums import BatchStatus, QrStatus, UserRole
from app.models.evidence import BlockchainRecord, LabEvidence, PackagingLot, QrToken
from app.models.hive import Harvest, HiveHarvest
from app.models.identity import User
from app.models.traceability import (
    Batch,
    BatchCollectionLot,
    CollectionLot,
    CollectionLotHarvest,
)
from app.packaging.service import _check_batch_read_authorization
from app.qr.schemas import (
    ConsumerBatchInfo,
    ConsumerBlockchainRecord,
    ConsumerLabEvidence,
    ConsumerPackagingInfo,
    ConsumerProvenanceHarvest,
    ConsumerVerificationResponse,
    QrTokenCreateResponse,
    QrTokenMetadataResponse,
)

HEX_TOKEN_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


def generate_qr_token(
    session: Session,
    packaging_lot_id: UUID,
    current_user: User,
    public_origin: str,
) -> QrTokenCreateResponse:
    """Generate a single-use verification QR token for a packaging lot under a finalized, active batch."""
    if current_user.role == UserRole.BEEKEEPER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Beekeepers cannot generate QR tokens",
        )

    if current_user.role not in (UserRole.ADMIN, UserRole.PROCESSOR):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to generate QR tokens",
        )

    # Concurrency locking: Lock PackagingLot row with FOR UPDATE
    lot = session.scalar(
        select(PackagingLot)
        .where(PackagingLot.id == packaging_lot_id)
        .with_for_update()
    )
    if lot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Packaging lot not found",
        )

    batch = session.scalar(select(Batch).where(Batch.id == lot.batch_id))
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch associated with packaging lot not found",
        )

    # Processor ownership check
    if current_user.role == UserRole.PROCESSOR and batch.processor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Processors can only generate QR tokens for their own batches",
        )

    # Batch prerequisites: Finalized and ACTIVE
    if not batch.is_finalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot generate QR token for an unfinalized batch; batch must be finalized first",
        )

    if batch.status != BatchStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot generate QR token for batch in {batch.status.value} status; must be ACTIVE",
        )

    # Ensure QR does not already exist for this lot (exactly once generation)
    existing_token = session.scalar(
        select(QrToken).where(QrToken.packaging_lot_id == lot.id)
    )
    if existing_token is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="QR token already exists for this packaging lot",
        )

    # Cryptographically secure 256-bit entropy token generation
    raw_token = secrets.token_hex(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest().lower()
    qr_id = uuid4()

    qr_token = QrToken(
        id=qr_id,
        packaging_lot_id=lot.id,
        token_hash=token_hash,
        status=QrStatus.ACTIVE,
    )
    session.add(qr_token)

    # Record AuditEvent (never contains raw token or token_hash)
    audit_event = AuditEvent(
        event_type="QR_GENERATED",
        entity_type="QR_TOKEN",
        entity_id=qr_id,
        actor_user_id=current_user.id,
        timestamp=datetime.now(UTC),
        metadata_json={
            "packaging_lot_id": str(lot.id),
            "batch_id": str(batch.id),
            "package_lot_code": lot.package_lot_code,
        },
    )
    session.add(audit_event)

    try:
        session.flush()
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="QR token already exists for this packaging lot",
        ) from exc

    session.refresh(qr_token)

    verification_url = f"{public_origin.rstrip('/')}/verify/{raw_token}"

    return QrTokenCreateResponse(
        id=qr_token.id,
        packaging_lot_id=qr_token.packaging_lot_id,
        status=qr_token.status,
        verification_url=verification_url,
        created_at=qr_token.created_at,
    )


def get_qr_token_metadata(
    session: Session,
    packaging_lot_id: UUID,
    current_user: User,
) -> QrTokenMetadataResponse:
    """Retrieve metadata for a packaging lot's QR token, enforcing RBAC."""
    lot = session.scalar(
        select(PackagingLot)
        .options(
            joinedload(PackagingLot.batch)
            .joinedload(Batch.collection_lot_links)
            .joinedload(BatchCollectionLot.collection_lot)
            .joinedload(CollectionLot.harvest_links)
            .joinedload(CollectionLotHarvest.harvest)
        )
        .where(PackagingLot.id == packaging_lot_id)
    )
    if lot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Packaging lot not found",
        )

    _check_batch_read_authorization(lot.batch, current_user)

    qr_token = session.scalar(
        select(QrToken).where(QrToken.packaging_lot_id == lot.id)
    )
    if qr_token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR token not found for this packaging lot",
        )

    return QrTokenMetadataResponse.model_validate(qr_token)


def revoke_qr_token(
    session: Session,
    qr_id: UUID,
    current_user: User,
) -> QrTokenMetadataResponse:
    """Revoke an active QR token. ADMIN only."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can revoke QR tokens",
        )

    qr_token = session.scalar(
        select(QrToken).where(QrToken.id == qr_id).with_for_update()
    )
    if qr_token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR token not found",
        )

    if qr_token.status != QrStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="QR token is already revoked and cannot be modified",
        )

    qr_token.status = QrStatus.REVOKED

    audit_event = AuditEvent(
        event_type="QR_REVOKED",
        entity_type="QR_TOKEN",
        entity_id=qr_token.id,
        actor_user_id=current_user.id,
        timestamp=datetime.now(UTC),
        metadata_json={
            "packaging_lot_id": str(qr_token.packaging_lot_id),
            "previous_status": "ACTIVE",
            "new_status": "REVOKED",
        },
    )
    session.add(audit_event)
    session.commit()
    session.refresh(qr_token)

    return QrTokenMetadataResponse.model_validate(qr_token)


def verify_consumer_token(
    session: Session,
    raw_token: str,
) -> ConsumerVerificationResponse:
    """Public verification endpoint returning a public-safe DTO without secrets or PII."""
    if not isinstance(raw_token, str) or len(raw_token) != 64 or not HEX_TOKEN_PATTERN.fullmatch(raw_token):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification record not found",
        )

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest().lower()

    qr_token = session.scalar(
        select(QrToken)
        .options(
            joinedload(QrToken.packaging_lot)
            .joinedload(PackagingLot.batch)
            .joinedload(Batch.collection_lot_links)
            .joinedload(BatchCollectionLot.collection_lot)
            .joinedload(CollectionLot.harvest_links)
            .joinedload(CollectionLotHarvest.harvest)
            .joinedload(Harvest.hive_links)
            .joinedload(HiveHarvest.hive)
        )
        .where(QrToken.token_hash == token_hash)
    )
    if qr_token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification record not found",
        )

    # Revoked tokens return 410 Gone
    if qr_token.status == QrStatus.REVOKED:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="QR token has been revoked",
        )

    lot = qr_token.packaging_lot
    batch = lot.batch if lot else None
    if batch is None or not batch.is_finalized:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verification record not found",
        )

    # Query public lab evidence and blockchain records for batch
    lab_records = session.scalars(
        select(LabEvidence)
        .where(LabEvidence.batch_id == batch.id)
        .order_by(LabEvidence.uploaded_at.desc())
    ).all()

    bc_records = session.scalars(
        select(BlockchainRecord)
        .where(BlockchainRecord.batch_id == batch.id)
        .order_by(BlockchainRecord.recorded_at.asc())
    ).all()

    # Determine public-safe verification status and warnings
    if batch.status == BatchStatus.HOLD:
        verification_status = "HOLD"
        warning = "Notice: This honey batch is currently on administrative HOLD. Distribution is temporarily paused."
    elif batch.status == BatchStatus.RECALL:
        verification_status = "RECALLED"
        warning = "WARNING: This honey batch has been RECALLED. Do not consume this product."
    else:
        verification_status = "VERIFIED"
        warning = None

    # Curate public-safe provenance (no coordinates, no beekeeper IDs)
    provenance_list: list[ConsumerProvenanceHarvest] = []
    seen_harvests: set[UUID] = set()
    for bcl in batch.collection_lot_links:
        for clh in bcl.collection_lot.harvest_links:
            h = clh.harvest
            if h.id not in seen_harvests:
                seen_harvests.add(h.id)
                regions = {
                    hh.hive.location_region
                    for hh in h.hive_links
                    if hh.hive and hh.hive.location_region
                }
                provenance_list.append(
                    ConsumerProvenanceHarvest(
                        harvest_code=h.harvest_code,
                        harvest_date=h.harvest_date,
                        regions=sorted(regions),
                    )
                )

    # Curate public-safe lab evidence (no filesystem paths)
    lab_list = [
        ConsumerLabEvidence(
            certificate_id=e.certificate_id,
            test_summary=e.test_summary,
            file_name=e.file_name,
            file_hash_sha256=e.file_hash_sha256,
            status=e.status,
            uploaded_at=e.uploaded_at,
        )
        for e in lab_records
    ]

    # Curate public-safe blockchain records (only on-chain tx references)
    bc_list = [
        ConsumerBlockchainRecord(
            event_type=r.event_type,
            transaction_hash=r.transaction_hash,
            status=r.status,
            network=r.network,
            contract_address=r.contract_address,
            block_number=r.block_number,
            recorded_at=r.recorded_at,
        )
        for r in bc_records
        if r.transaction_hash is not None
    ]

    return ConsumerVerificationResponse(
        verification_status=verification_status,
        batch=ConsumerBatchInfo(
            batch_code=batch.batch_code,
            status=batch.status,
            is_finalized=batch.is_finalized,
            finalized_at=batch.finalized_at,
            created_at=batch.created_at,
        ),
        packaging_lot=ConsumerPackagingInfo(
            package_lot_code=lot.package_lot_code,
            quantity=lot.quantity,
            unit=lot.unit,
            package_size_grams=float(lot.package_size_grams),
            packaged_quantity_kg=lot.packaged_quantity_kg,
            created_at=lot.created_at,
        ),
        provenance=provenance_list,
        lab_evidence=lab_list,
        blockchain_records=bc_list,
        warning=warning,
    )
