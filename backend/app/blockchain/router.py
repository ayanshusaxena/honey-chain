"""FastAPI router for Blockchain audit and evidence recording endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth.dependencies import get_current_user, require_roles
from app.blockchain.config import (
    BlockchainClientError,
    BlockchainNotConfiguredError,
    BlockchainTransactionError,
)
from app.blockchain.schemas import BlockchainRecordResponse
from app.blockchain.service import BlockchainService, get_blockchain_service
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.evidence import LabEvidence
from app.models.hive import Harvest
from app.models.identity import User
from app.models.traceability import Batch, BatchCollectionLot, CollectionLot, CollectionLotHarvest

router = APIRouter(tags=["blockchain"])


def get_service() -> BlockchainService:
    """Dependency provider for BlockchainService."""
    return get_blockchain_service()


def _check_batch_read_authorization(batch: Batch, user: User) -> None:
    """Verify user has read authorization for the batch's blockchain records."""
    if user.role == UserRole.ADMIN:
        return

    if user.role == UserRole.PROCESSOR:
        if batch.processor_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to view blockchain records for this batch",
            )
        return

    if user.role == UserRole.BEEKEEPER:
        has_harvest_in_batch = False
        for lot_link in batch.collection_lot_links:
            for harv_link in lot_link.collection_lot.harvest_links:
                if harv_link.harvest.created_by_id == user.id:
                    has_harvest_in_batch = True
                    break
            if has_harvest_in_batch:
                break

        if not has_harvest_in_batch:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to view blockchain records for this batch",
            )
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient permissions",
    )


# ===========================================================================
# Batch Registration On-Chain
# ===========================================================================

@router.post(
    "/batches/{batch_id}/blockchain-register",
    response_model=BlockchainRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a processing batch on the blockchain contract",
)
@router.post(
    "/batches/{batch_id}/blockchain",
    response_model=BlockchainRecordResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def register_batch_on_chain_endpoint(
    batch_id: UUID,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROCESSOR)),
    service: BlockchainService = Depends(get_service),
) -> BlockchainRecordResponse:
    """Submit an on-chain batch registration transaction for an existing batch."""
    batch = session.scalar(select(Batch).where(Batch.id == batch_id))
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )

    # PROCESSOR ownership check: processors may only register their own batches
    if current_user.role == UserRole.PROCESSOR and batch.processor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Processors can only register their own batches on-chain",
        )

    try:
        record = service.register_batch_on_chain(
            session=session,
            batch_id=batch.id,
            actor_user_id=current_user.id,
        )
    except BlockchainNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Blockchain integration is not configured or disabled.",
        ) from exc
    except (BlockchainClientError, BlockchainTransactionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Blockchain transaction failed or was reverted on-chain.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return BlockchainRecordResponse.model_validate(record)


# ===========================================================================
# Lab Evidence Hash Recording On-Chain
# ===========================================================================

@router.post(
    "/lab-evidence/{evidence_id}/blockchain-record",
    response_model=BlockchainRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a verified lab evidence SHA-256 certificate hash on the blockchain contract",
)
@router.post(
    "/lab-evidence/{evidence_id}/blockchain",
    response_model=BlockchainRecordResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def record_lab_evidence_on_chain_endpoint(
    evidence_id: UUID,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PROCESSOR)),
    service: BlockchainService = Depends(get_service),
) -> BlockchainRecordResponse:
    """Submit an on-chain lab evidence hash recording transaction for an existing certificate."""
    evidence = session.scalar(select(LabEvidence).where(LabEvidence.id == evidence_id))
    if evidence is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab evidence not found",
        )

    batch = session.scalar(select(Batch).where(Batch.id == evidence.batch_id))
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch associated with lab evidence not found",
        )

    # PROCESSOR ownership check: processors may only record evidence for their own batches
    if current_user.role == UserRole.PROCESSOR and batch.processor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Processors can only record lab evidence for their own batches",
        )

    try:
        record = service.add_evidence_on_chain(
            session=session,
            evidence_id=evidence.id,
            actor_user_id=current_user.id,
        )
    except BlockchainNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Blockchain integration is not configured or disabled.",
        ) from exc
    except (BlockchainClientError, BlockchainTransactionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Blockchain transaction failed or was reverted on-chain.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return BlockchainRecordResponse.model_validate(record)


# ===========================================================================
# Query Blockchain Records for Batch
# ===========================================================================

@router.get(
    "/batches/{batch_id}/blockchain-records",
    response_model=list[BlockchainRecordResponse],
    status_code=status.HTTP_200_OK,
    summary="Retrieve all blockchain audit records for a processing batch",
)
@router.get(
    "/batches/{batch_id}/blockchain",
    response_model=list[BlockchainRecordResponse],
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def list_batch_blockchain_records_endpoint(
    batch_id: UUID,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    service: BlockchainService = Depends(get_service),
) -> list[BlockchainRecordResponse]:
    """Retrieve all on-chain audit records for a batch, checking lineage permissions."""
    batch = session.scalar(
        select(Batch)
        .options(
            joinedload(Batch.collection_lot_links)
            .joinedload(BatchCollectionLot.collection_lot)
            .joinedload(CollectionLot.harvest_links)
            .joinedload(CollectionLotHarvest.harvest)
        )
        .where(Batch.id == batch_id)
    )
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )

    _check_batch_read_authorization(batch, current_user)

    records = service.get_batch_blockchain_records(session, batch_id)
    return [BlockchainRecordResponse.model_validate(r) for r in records]
