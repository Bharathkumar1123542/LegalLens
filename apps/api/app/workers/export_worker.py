"""
Export Worker — LegalLens Phase 5
Implements: architecture.md §5.8 export generation (summary, checklist, lawyer_brief, comparison_report).

Background task for generating exports in various formats (PDF, DOCX, Markdown)
and uploading to S3.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.workers import celery_app, AsyncTask
from app.db.session import get_async_session
from app.models.export import ExportArtifact
from app.services.export import generate_export
from app.services.audit import record_audit_event

log = structlog.get_logger(__name__)


@celery_app.task(name="generate_export", base=AsyncTask, bind=True, max_retries=3)
async def generate_export_task(self, export_id: str) -> dict:
    """
    Generate an export artifact and upload to S3.
    
    Args:
        export_id: UUID of ExportArtifact to generate
    
    Returns:
        dict with storage_key and file_size_bytes
    
    Raises:
        Exception: On unrecoverable errors (marks export as failed)
    
    Status transitions:
        queued → generating → ready/failed
    """
    export_uuid = uuid.UUID(export_id)
    
    async with get_async_session() as db:
        try:
            # Fetch export artifact
            result = await db.execute(
                select(ExportArtifact)
                .options(
                    selectinload(ExportArtifact.document),
                    selectinload(ExportArtifact.comparison_job),
                )
                .where(ExportArtifact.id == export_uuid)
            )
            export: ExportArtifact | None = result.scalar_one_or_none()
            
            if not export:
                log.error("export.artifact_not_found", export_id=export_id)
                raise ValueError(f"ExportArtifact {export_id} not found")
            
            if export.status != "queued":
                log.warning(
                    "export.invalid_status",
                    export_id=export_id,
                    status=export.status,
                )
                return {"skipped": True, "reason": f"Export already {export.status}"}
            
            # Update status to generating
            export.status = "generating"
            await db.commit()
            
            log.info(
                "export.started",
                export_id=export_id,
                export_type=export.export_type,
                file_format=export.file_format,
                document_id=str(export.document_id) if export.document_id else None,
                comparison_job_id=str(export.comparison_job_id) if export.comparison_job_id else None,
            )
            
            # Generate export via service
            storage_key, file_size = await generate_export(db=db, export_id=export_uuid)
            
            # Update export record
            export.status = "ready"
            export.storage_key = storage_key
            await db.commit()
            
            # Audit log
            await record_audit_event(
                db=db,
                actor_id=export.owner_id,
                action="export.artifact_generated",
                resource_type="export_artifact",
                resource_id=export_uuid,
                metadata={
                    "export_type": export.export_type,
                    "file_format": export.file_format,
                    "file_size_bytes": file_size,
                    "storage_key": storage_key,
                },
                ip_address="system",
            )
            
            log.info(
                "export.completed",
                export_id=export_id,
                storage_key=storage_key,
                file_size_bytes=file_size,
            )
            
            return {
                "storage_key": storage_key,
                "file_size_bytes": file_size,
            }
            
        except Exception as exc:
            log.error(
                "export.failed",
                export_id=export_id,
                error=str(exc),
                exc_info=True,
            )
            
            # Mark export as failed
            async with get_async_session() as db:
                result = await db.execute(
                    select(ExportArtifact).where(ExportArtifact.id == export_uuid)
                )
                export = result.scalar_one_or_none()
                if export:
                    export.status = "failed"
                    await db.commit()
            
            # Retry on transient failures (LLM API, S3 upload)
            if any(
                keyword in str(exc).lower()
                for keyword in ["api", "rate_limit", "timeout", "s3", "connection"]
            ):
                raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
            
            raise
