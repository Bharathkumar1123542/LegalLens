"""
Extraction Worker — LegalLens Phase 3
Implements: architecture.md §5.4 clause extraction with keyword pre-filter + LLM classification.

Background task for extracting clauses from document chunks.
Status: queued → extracting → completed/failed
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.workers import celery_app, AsyncTask
from app.db.session import get_async_session
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.clause import Clause
from app.services.clause_extraction import extract_clauses_from_chunks
from app.services.audit import record_audit_event

log = structlog.get_logger(__name__)


@celery_app.task(name="extract_clauses", base=AsyncTask, bind=True, max_retries=3)
async def extract_clauses_task(
    self,
    document_id: str,
    clause_types: list[str] | None = None,
) -> dict:
    """
    Extract clauses from document chunks using LLM classification.
    
    Args:
        document_id: UUID of document to process
        clause_types: Optional list of specific clause types to extract.
                     If None, extracts all 10 types.
    
    Returns:
        dict with extraction_count and clause_types_found
    
    Raises:
        Exception: On unrecoverable errors (marks document extraction as failed)
    """
    doc_uuid = uuid.UUID(document_id)
    
    async with get_async_session() as db:
        try:
            # Fetch document with chunks
            result = await db.execute(
                select(Document)
                .options(selectinload(Document.chunks))
                .where(Document.id == doc_uuid)
            )
            doc: Document | None = result.scalar_one_or_none()
            
            if not doc:
                log.error("extraction.document_not_found", document_id=document_id)
                raise ValueError(f"Document {document_id} not found")
            
            if doc.status != "ready":
                log.error(
                    "extraction.invalid_status",
                    document_id=document_id,
                    status=doc.status,
                )
                raise ValueError(f"Document must be ready, got status={doc.status}")
            
            log.info(
                "extraction.started",
                document_id=document_id,
                chunk_count=len(doc.chunks),
                clause_types=clause_types,
            )
            
            # Extract clauses
            clauses = await extract_clauses_from_chunks(
                db=db,
                document_id=doc_uuid,
                clause_types=clause_types,
            )
            
            # Commit clauses to database
            for clause_dict in clauses:
                clause = Clause(
                    id=uuid.uuid4(),
                    document_id=doc_uuid,
                    chunk_id=clause_dict["chunk_id"],
                    clause_type=clause_dict["clause_type"],
                    text=clause_dict["text"],
                    offset_start=clause_dict["offset_start"],
                    offset_end=clause_dict["offset_end"],
                    risk_level=clause_dict["risk_level"],
                    explanation=clause_dict["explanation"],
                    page_number=clause_dict.get("page_number"),
                )
                db.add(clause)
            
            await db.commit()
            
            # Audit log
            clause_types_found = list(set(c["clause_type"] for c in clauses))
            await record_audit_event(
                db=db,
                actor_id=doc.owner_id,
                action="clause.extraction_completed",
                resource_type="document",
                resource_id=doc_uuid,
                metadata={
                    "extraction_count": len(clauses),
                    "clause_types_found": clause_types_found,
                },
                ip_address="system",
            )
            
            log.info(
                "extraction.completed",
                document_id=document_id,
                extraction_count=len(clauses),
                clause_types_found=clause_types_found,
            )
            
            return {
                "extraction_count": len(clauses),
                "clause_types_found": clause_types_found,
            }
            
        except Exception as exc:
            log.error(
                "extraction.failed",
                document_id=document_id,
                error=str(exc),
                exc_info=True,
            )
            
            # Retry on transient LLM API failures
            if "API" in str(exc) or "rate_limit" in str(exc).lower():
                raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
            
            raise
