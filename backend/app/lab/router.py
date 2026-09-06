"""FastAPI router for Lab Evidence endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.database import get_db
from app.lab.schemas import LabEvidenceResponse, LabEvidenceVerifyResponse
from app.lab.service import (
    create_lab_evidence,
    download_lab_evidence_file,
    get_batch_lab_evidence,
    get_lab_evidence_by_id,
    verify_lab_evidence_hash,
)
from app.models.identity import User

router = APIRouter(tags=["lab-evidence"])


@router.post(
    "/batches/{batch_id}/lab-evidence",
    response_model=LabEvidenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a lab evidence certificate for a processing batch",
)
def upload_batch_lab_evidence(
    batch_id: UUID,
    certificate_id: str = Form(...),
    test_summary: str = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LabEvidenceResponse:
    """Upload and attach a PDF lab evidence certificate to a processing batch."""
    return create_lab_evidence(
        session=session,
        batch_id=batch_id,
        certificate_id=certificate_id,
        test_summary=test_summary,
        file=file,
        current_user=current_user,
    )


@router.get(
    "/batches/{batch_id}/lab-evidence",
    response_model=list[LabEvidenceResponse],
    status_code=status.HTTP_200_OK,
    summary="List all lab evidence records for a processing batch",
)
def list_batch_lab_evidence(
    batch_id: UUID,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[LabEvidenceResponse]:
    """Retrieve all lab evidence records attached to the specified batch."""
    return get_batch_lab_evidence(
        session=session,
        batch_id=batch_id,
        current_user=current_user,
    )


@router.get(
    "/lab-evidence/{evidence_id}",
    response_model=LabEvidenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a single lab evidence record by ID",
)
def get_lab_evidence(
    evidence_id: UUID,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LabEvidenceResponse:
    """Retrieve metadata for a specific lab evidence record."""
    return get_lab_evidence_by_id(
        session=session,
        evidence_id=evidence_id,
        current_user=current_user,
    )


@router.get(
    "/lab-evidence/{evidence_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Download the certificate PDF file for a lab evidence record",
)
def download_lab_evidence(
    evidence_id: UUID,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """Stream and download the physical PDF certificate file."""
    file_path, filename = download_lab_evidence_file(
        session=session,
        evidence_id=evidence_id,
        current_user=current_user,
    )
    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=filename,
    )


@router.get(
    "/lab-evidence/{evidence_id}/verify",
    response_model=LabEvidenceVerifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify that physical evidence artifact on disk matches recorded SHA-256 hash",
)
def verify_lab_evidence(
    evidence_id: UUID,
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LabEvidenceVerifyResponse:
    """Verify stored evidence file against recorded SHA-256 hash and return claim statement."""
    return verify_lab_evidence_hash(
        session=session,
        evidence_id=evidence_id,
        current_user=current_user,
    )
