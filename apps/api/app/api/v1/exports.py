"""
Exports API endpoints — LegalLens Phase 5
Implements: architecture.md §8 export endpoints.
Routes: POST /exports, GET /exports/{id}
"""

import logging
import uuid

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbDep
from app.models.export import ExportArtifact
from app.schemas.export import (
    CreateExportRequest,
    ExportCreatedResponse,
    ExportArtifactResponse,
)
from app.services.audit import record_audit_event
from app.services.storage import generate_presigned_url
from app.workers.export_worker import generate_export_task

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/exports", tags=["exports"])


@router.post(
    "",
    response_model=ExportCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create an export job",
    responses={
        400: {"description": "Invalid request (must have document_id OR comparison_job_id)"},
        409: {"description": "Source not ready for export"},
    },
)
async def create_export_endpoint(
    request_body: CreateExportRequest,
    request: Request,
    current_user: CurrentUser,
    db: DbDep,
) -> ExportCreatedResponse:
    """
    Create an export artifact job.
    
    Per architecture.md §5.8:
    - Specify export_type: summary, checklist, lawyer_brief, comparison_report
    - Specify file_format: pdf, docx, md
    - Provide either document_id OR comparison_job_id (not both)
    
    Returns 202 immediately. Poll GET /exports/{id} for status and download URL.
    """
    # Audit the export request
    ip = request.client.host if request.client else "unknown"
    await record_audit_event(
        db=db,
        actor_id=current_user.id,
        action="export.create",
        resource_type="export_artifact",
        resource_id=uuid.uuid4(),
        metadata={
            "export_type": request_body.export_type,
            "file_format": request_body.file_format,
        },
        ip_address=ip,
    )
    
    try:
        # Create export artifact
        export_artifact = ExportArtifact(
            owner_id=current_user.id,
            document_id=request_body.document_id,
            comparison_job_id=request_body.comparison_job_id,
            export_type=request_body.export_type,
            file_format=request_body.file_format,
            status="queued",
        )
        
        db.add(export_artifact)
        await db.commit()
        await db.refresh(export_artifact)
        
        logger.info(
            f"export.created: export={export_artifact.id}, "
            f"type={request_body.export_type}, format={request_body.file_format}"
        )
        
        # Enqueue async processing via Celery
        generate_export_task.delay(export_id=str(export_artifact.id))
        
        return ExportCreatedResponse(
            export_id=export_artifact.id,
            status=export_artifact.status,
        )
        
    except Exception as e:
        logger.error(
            f"export.creation_error: user={current_user.id}, error={e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create export job",
        ) from e


@router.get(
    "/{export_id}",
    response_model=ExportArtifactResponse,
    status_code=status.HTTP_200_OK,
    summary="Get export status and download URL",
    responses={
        404: {"description": "Export not found"},
        403: {"description": "Not authorized to access this export"},
    },
)
async def get_export_endpoint(
    export_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
) -> ExportArtifactResponse:
    """
    Retrieve export artifact status and download URL.
    
    Returns:
    - Export metadata (type, format, status)
    - Signed S3 download URL (when status=ready, valid for 1 hour)
    
    Poll this endpoint until status=ready to get download URL.
    """
    # Get export artifact
    result = await db.execute(
        select(ExportArtifact).where(ExportArtifact.id == export_id)
    )
    export_artifact = result.scalar_one_or_none()
    
    if not export_artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export {export_id} not found",
        )
    
    # Verify ownership
    if export_artifact.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this export",
        )
    
    # Generate signed URL if ready
    download_url = None
    if export_artifact.status == "ready" and export_artifact.storage_key:
        try:
            download_url = await generate_presigned_url(
                key=export_artifact.storage_key,
                expiration=3600,  # 1 hour
            )
        except Exception as e:
            logger.error(
                f"export.presigned_url_error: export={export_id}, error={e}"
            )
    
    logger.info(
        f"export.retrieved: export={export_id}, status={export_artifact.status}"
    )
    
    # Build response
    response = ExportArtifactResponse(
        id=export_artifact.id,
        owner_id=export_artifact.owner_id,
        document_id=export_artifact.document_id,
        comparison_job_id=export_artifact.comparison_job_id,
        export_type=export_artifact.export_type,
        file_format=export_artifact.file_format,
        status=export_artifact.status,
        storage_key=export_artifact.storage_key,
        created_at=export_artifact.created_at,
        download_url=download_url,
    )
    
    return response
