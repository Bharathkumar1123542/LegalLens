"""
Comparisons API endpoints — LegalLens Phase 5
Implements: architecture.md §8 comparison endpoints.
Routes: POST /comparisons, GET /comparisons/{id}
"""

import logging
import uuid

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbDep
from app.models.comparison import ComparisonJob, ComparisonResult
from app.schemas.comparison import (
    CreateComparisonRequest,
    ComparisonJobCreatedResponse,
    ComparisonJobResponse,
    ComparisonResultResponse,
)
from app.services import comparison as comparison_service
from app.services.audit import record_audit_event
from app.workers.comparison_worker import run_comparison_task

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/comparisons", tags=["comparisons"])


@router.post(
    "",
    response_model=ComparisonJobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a comparison job for 2-5 documents",
    responses={
        400: {"description": "Invalid document count or documents not ready"},
        403: {"description": "Not authorized to access documents"},
    },
)
async def create_comparison_endpoint(
    request_body: CreateComparisonRequest,
    request: Request,
    current_user: CurrentUser,
    db: DbDep,
) -> ComparisonJobCreatedResponse:
    """
    Create a clause-aligned comparison job.
    
    Per architecture.md §5.6:
    - Validates 2-5 documents
    - All documents must be owned by user and status=ready
    - Returns 202 immediately, processing happens async
    
    Poll GET /comparisons/{id} to retrieve results.
    """
    # Audit the comparison request
    ip = request.client.host if request.client else "unknown"
    await record_audit_event(
        db=db,
        actor_id=current_user.id,
        action="comparison.create",
        resource_type="comparison_job",
        resource_id=uuid.uuid4(),  # Placeholder, actual ID created below
        metadata={"document_count": len(request_body.document_ids)},
        ip_address=ip,
    )
    
    try:
        # Create comparison job
        logger.info(
            f"comparison.create: user={current_user.id}, "
            f"documents={len(request_body.document_ids)}"
        )
        
        job = await comparison_service.create_comparison_job(
            db=db,
            owner_id=current_user.id,
            document_ids=request_body.document_ids,
        )
        
        logger.info(
            f"comparison.created: job={job.id}, user={current_user.id}"
        )
        
        # Enqueue async processing via Celery
        run_comparison_task.delay(comparison_job_id=str(job.id))
        
        return ComparisonJobCreatedResponse(
            comparison_job_id=job.id,
            status=job.status,
        )
        
    except ValueError as e:
        # Validation errors (document not found, not ready, etc.)
        logger.error(
            f"comparison.validation_error: user={current_user.id}, error={e}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    
    except Exception as e:
        logger.error(
            f"comparison.unexpected_error: user={current_user.id}, error={e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create comparison job",
        ) from e


@router.get(
    "/{comparison_job_id}",
    response_model=ComparisonJobResponse,
    status_code=status.HTTP_200_OK,
    summary="Get comparison job status and results",
    responses={
        404: {"description": "Comparison job not found"},
        403: {"description": "Not authorized to access this comparison"},
    },
)
async def get_comparison_endpoint(
    comparison_job_id: uuid.UUID,
    current_user: CurrentUser,
    db: DbDep,
) -> ComparisonJobResponse:
    """
    Retrieve comparison job status and results.
    
    Returns:
    - Job metadata (status, created_at, completed_at)
    - Results list (when status=completed)
    - Each result includes clause_type, excerpts, diff_summary, materiality
    """
    # Get comparison job
    result = await db.execute(
        select(ComparisonJob).where(ComparisonJob.id == comparison_job_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison job {comparison_job_id} not found",
        )
    
    # Verify ownership
    if job.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this comparison job",
        )
    
    # Get results if completed
    results = []
    if job.status == "completed":
        results_query = await db.execute(
            select(ComparisonResult)
            .where(ComparisonResult.comparison_job_id == comparison_job_id)
            .order_by(
                ComparisonResult.materiality.desc(),
                ComparisonResult.clause_type,
            )
        )
        db_results = results_query.scalars().all()
        results = [ComparisonResultResponse.model_validate(r) for r in db_results]
    
    logger.info(
        f"comparison.retrieved: job={comparison_job_id}, "
        f"status={job.status}, results={len(results)}"
    )
    
    # Build response
    response = ComparisonJobResponse(
        id=job.id,
        owner_id=job.owner_id,
        status=job.status,
        created_at=job.created_at,
        completed_at=job.completed_at,
        results=results,
    )
    
    return response
