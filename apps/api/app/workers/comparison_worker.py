"""
Comparison Worker — LegalLens Phase 5
Implements: architecture.md §5.6 clause-aligned comparison across 2-5 documents.

Background task for comparing documents by aligning clauses and generating
materiality ratings using Claude LLM.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.workers import celery_app, AsyncTask
from app.db.session import get_async_session
from app.models.comparison import ComparisonJob
from app.services.comparison import run_comparison
from app.services.audit import record_audit_event

log = structlog.get_logger(__name__)


@celery_app.task(name="run_comparison", base=AsyncTask, bind=True, max_retries=3)
async def run_comparison_task(self, comparison_job_id: str) -> dict:
    """
    Execute a comparison job: align clauses across documents and generate diffs.
    
    Args:
        comparison_job_id: UUID of ComparisonJob to process
    
    Returns:
        dict with result_count and materiality_distribution
    
    Raises:
        Exception: On unrecoverable errors (marks job as failed)
    
    Status transitions:
        queued → running → completed/failed
    """
    job_uuid = uuid.UUID(comparison_job_id)
    
    async with get_async_session() as db:
        try:
            # Fetch comparison job
            result = await db.execute(
                select(ComparisonJob)
                .options(selectinload(ComparisonJob.documents))
                .where(ComparisonJob.id == job_uuid)
            )
            job: ComparisonJob | None = result.scalar_one_or_none()
            
            if not job:
                log.error("comparison.job_not_found", job_id=comparison_job_id)
                raise ValueError(f"ComparisonJob {comparison_job_id} not found")
            
            if job.status != "queued":
                log.warning(
                    "comparison.invalid_status",
                    job_id=comparison_job_id,
                    status=job.status,
                )
                return {"skipped": True, "reason": f"Job already {job.status}"}
            
            # Update status to running
            job.status = "running"
            await db.commit()
            
            log.info(
                "comparison.started",
                job_id=comparison_job_id,
                document_count=len(job.documents),
            )
            
            # Run comparison service
            results = await run_comparison(db=db, comparison_job_id=job_uuid)
            
            # Update status to completed
            job.status = "completed"
            job.completed_at = db.execute(select(db.func.now())).scalar()
            await db.commit()
            
            # Calculate materiality distribution
            materiality_counts = {}
            for result in results:
                mat = result.materiality
                materiality_counts[mat] = materiality_counts.get(mat, 0) + 1
            
            # Audit log
            await record_audit_event(
                db=db,
                actor_id=job.owner_id,
                action="comparison.job_completed",
                resource_type="comparison_job",
                resource_id=job_uuid,
                metadata={
                    "result_count": len(results),
                    "document_count": len(job.documents),
                    "materiality_distribution": materiality_counts,
                },
                ip_address="system",
            )
            
            log.info(
                "comparison.completed",
                job_id=comparison_job_id,
                result_count=len(results),
                materiality_distribution=materiality_counts,
            )
            
            return {
                "result_count": len(results),
                "materiality_distribution": materiality_counts,
            }
            
        except Exception as exc:
            log.error(
                "comparison.failed",
                job_id=comparison_job_id,
                error=str(exc),
                exc_info=True,
            )
            
            # Mark job as failed
            async with get_async_session() as db:
                result = await db.execute(
                    select(ComparisonJob).where(ComparisonJob.id == job_uuid)
                )
                job = result.scalar_one_or_none()
                if job:
                    job.status = "failed"
                    await db.commit()
            
            # Retry on transient LLM API failures
            if "API" in str(exc) or "rate_limit" in str(exc).lower() or "timeout" in str(exc).lower():
                raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
            
            raise
