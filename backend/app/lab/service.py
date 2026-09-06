"""Service layer for Lab Evidence domain operations."""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.lab.schemas import LabEvidenceVerifyResponse
from app.models.audit import AuditEvent
from app.models.enums import LabEvidenceStatus, UserRole
from app.models.evidence import LabEvidence
from app.models.hive import Harvest
from app.models.identity import User
from app.models.traceability import Batch, BatchCollectionLot, CollectionLot, CollectionLotHarvest

# 10 MB maximum file size
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

# Storage path: backend/uploads/lab_evidence/
STORAGE_DIR = Path(__file__).resolve().parents[2] / "uploads" / "lab_evidence"


def _check_batch_read_authorization(batch: Batch, user: User) -> None:
    """Verify that user has authorization to read batch metadata and evidence."""
    if user.role == UserRole.ADMIN:
        return

    if user.role == UserRole.PROCESSOR:
        if batch.processor_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to view evidence for this batch",
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
                detail="Insufficient permissions to view evidence for this batch",
            )
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient permissions to view evidence for this batch",
    )


def create_lab_evidence(
    session: Session,
    batch_id: UUID,
    certificate_id: str,
    test_summary: str,
    file: UploadFile,
    current_user: User,
) -> LabEvidence:
    """Validate, hash, store, and record a new lab evidence certificate."""
    # Gate 1: Role check for creation
    if current_user.role == UserRole.BEEKEEPER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Beekeepers cannot upload lab evidence",
        )

    # Retrieve target batch
    batch = session.scalar(select(Batch).where(Batch.id == batch_id))
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found",
        )

    # Gate 1: Processor ownership check
    if current_user.role == UserRole.PROCESSOR and batch.processor_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Processors can only upload lab evidence for their own batches",
        )

    # Uniqueness check on certificate_id
    existing_cert = session.scalar(
        select(LabEvidence).where(LabEvidence.certificate_id == certificate_id)
    )
    if existing_cert is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Certificate ID already exists",
        )

    # Validate file format: Require .pdf filename
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF documents (.pdf) are allowed for lab evidence",
        )

    # Read uploaded bytes synchronously from SpooledTemporaryFile
    file_bytes = file.file.read()
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file cannot be empty",
        )

    # Verify uploaded bytes begin with the PDF signature %PDF-
    if not file_bytes.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is not a valid PDF document (missing %PDF- signature)",
        )

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds maximum allowed size of 10 MB",
        )

    # Server-side SHA-256 over actual uploaded bytes (lowercase 64-char hex)
    file_hash_sha256 = hashlib.sha256(file_bytes).hexdigest().lower()

    # Ensure storage directory exists
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    evidence_id = uuid4()
    sanitized_name = Path(filename).name if filename else "report.pdf"
    stored_filename = f"{evidence_id}_{sanitized_name}"
    target_path = STORAGE_DIR / stored_filename

    try:
        target_path.write_bytes(file_bytes)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to persist evidence file: {exc}",
        ) from exc

    # Relative path stored for portability
    stored_rel_path = f"backend/uploads/lab_evidence/{stored_filename}"

    evidence = LabEvidence(
        id=evidence_id,
        batch_id=batch.id,
        certificate_id=certificate_id,
        test_summary=test_summary,
        file_name=sanitized_name,
        file_path=stored_rel_path,
        file_hash_sha256=file_hash_sha256,
        status=LabEvidenceStatus.ACTIVE,
        uploaded_at=datetime.now(UTC),
    )
    session.add(evidence)

    # Record AuditEvent: LAB_EVIDENCE_UPLOADED
    audit_event = AuditEvent(
        event_type="LAB_EVIDENCE_UPLOADED",
        entity_type="LAB_EVIDENCE",
        entity_id=evidence.id,
        actor_user_id=current_user.id,
        timestamp=datetime.now(UTC),
        metadata_json={
            "batch_id": str(batch.id),
            "certificate_id": certificate_id,
            "file_name": evidence.file_name,
            "file_hash_sha256": file_hash_sha256,
        },
    )
    session.add(audit_event)

    try:
        session.commit()
        session.refresh(evidence)
    except IntegrityError as exc:
        session.rollback()
        if target_path.exists():
            try:
                target_path.unlink()
            except OSError:
                pass
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Certificate ID already exists",
        ) from exc
    except Exception:
        session.rollback()
        # Clean up file on disk if DB transaction failed
        if target_path.exists():
            try:
                target_path.unlink()
            except OSError:
                pass
        raise

    return evidence


def get_batch_lab_evidence(
    session: Session,
    batch_id: UUID,
    current_user: User,
) -> list[LabEvidence]:
    """Retrieve all lab evidence records attached to a batch with lineage RBAC."""
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

    evidence_records = session.scalars(
        select(LabEvidence)
        .where(LabEvidence.batch_id == batch_id)
        .order_by(LabEvidence.uploaded_at.desc())
    ).all()

    return list(evidence_records)


def get_lab_evidence_by_id(
    session: Session,
    evidence_id: UUID,
    current_user: User,
) -> LabEvidence:
    """Retrieve a single lab evidence record by ID with batch lineage RBAC."""
    evidence = session.scalar(
        select(LabEvidence)
        .options(
            joinedload(LabEvidence.batch)
            .joinedload(Batch.collection_lot_links)
            .joinedload(BatchCollectionLot.collection_lot)
            .joinedload(CollectionLot.harvest_links)
            .joinedload(CollectionLotHarvest.harvest)
        )
        .where(LabEvidence.id == evidence_id)
    )
    if evidence is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab evidence not found",
        )

    _check_batch_read_authorization(evidence.batch, current_user)
    return evidence


def download_lab_evidence_file(
    session: Session,
    evidence_id: UUID,
    current_user: User,
) -> tuple[Path, str]:
    """Retrieve the physical file path and original filename for download."""
    evidence = get_lab_evidence_by_id(session, evidence_id, current_user)

    file_path = Path(evidence.file_path)
    if not file_path.is_absolute():
        # Resolve against repo root
        repo_root = Path(__file__).resolve().parents[3]
        file_path = repo_root / evidence.file_path

    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence file not found on disk",
        )

    return file_path, evidence.file_name


def verify_lab_evidence_hash(
    session: Session,
    evidence_id: UUID,
    current_user: User,
) -> LabEvidenceVerifyResponse:
    """Verify that physical evidence artifact on disk matches recorded SHA-256 hash."""
    evidence = get_lab_evidence_by_id(session, evidence_id, current_user)

    file_path = Path(evidence.file_path)
    if not file_path.is_absolute():
        repo_root = Path(__file__).resolve().parents[3]
        file_path = repo_root / evidence.file_path

    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence file not found on disk",
        )

    file_bytes = file_path.read_bytes()
    computed_hash = hashlib.sha256(file_bytes).hexdigest().lower()
    is_valid = (computed_hash == evidence.file_hash_sha256)

    return LabEvidenceVerifyResponse(
        id=evidence.id,
        evidence_id=evidence.id,
        batch_id=evidence.batch_id,
        certificate_id=evidence.certificate_id,
        file_name=evidence.file_name,
        file_hash_sha256=evidence.file_hash_sha256,
        computed_hash_sha256=computed_hash,
        is_hash_verified=is_valid,
        is_verified=is_valid,
        status=evidence.status,
        claim="The evidence artifact was recorded and its hash is verifiable.",
        claim_statement="The evidence artifact was recorded and its hash is verifiable.",
    )
