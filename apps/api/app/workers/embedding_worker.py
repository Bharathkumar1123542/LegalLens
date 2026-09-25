"""
Embedding Worker — LegalLens Phase 2
Implements: architecture.md §3 step 4 (generate embeddings for document chunks).

Background task for generating Voyage AI embeddings and storing in pgvector.
Can be triggered independently if embeddings need regeneration.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select

from app.workers import celery_app, AsyncTask
from app.db.session import get_async_session
from app.models.document import Document
from app.services.embedding import embed_chunks
from app.services.audit import record_audit_event

log = structlog.get_logger(__name__)


@celery_app.task(name="embed_document", base=AsyncTask, bind=True, max_retries=3)
async def embed_document_task(self, document_id: str) -> dict:
    """
    Generate embeddings for all chunks of a document.
    
    This task is typically called as part of the ingestion pipeline
    (process_document_task), but can also be invoked independently to
    regenerate embeddings (e.g., if switching embedding models).
    
    Args:
        document_id: UUID of document to embed
    
    Returns:
        dict with chunk_count and embedding_dimension
    
    Raises:
        Exception: On unrecoverable errors
    """
    doc_uuid = uuid.UUID(document_id)
    
    async with get_async_session() as db:
        try:
            # Fetch document
            result = await db.execute(
                select(Document).where(Document.id == doc_uuid)
            )
            doc: Document | None = result.scalar_one_or_none()
            
            if not doc:
                log.error("embedding.document_not_found", document_id=document_id)
                raise ValueError(f"Document {document_id} not found")
            
            log.info(
                "embedding.started",
                document_id=document_id,
            )
            
            # Generate embeddings
            chunk_count = await embed_chunks(db=db, document_id=doc_uuid)
            
            # Audit log
            await record_audit_event(
                db=db,
                actor_id=doc.owner_id,
                action="document.embeddings_generated",
                resource_type="document",
                resource_id=doc_uuid,
                metadata={
                    "chunk_count": chunk_count,
                    "embedding_model": "voyage-context-4",
                    "embedding_dimension": 1024,
                },
                ip_address="system",
            )
            
            log.info(
                "embedding.completed",
                document_id=document_id,
                chunk_count=chunk_count,
            )
            
            return {
                "chunk_count": chunk_count,
                "embedding_dimension": 1024,
            }
            
        except Exception as exc:
            log.error(
                "embedding.failed",
                document_id=document_id,
                error=str(exc),
                exc_info=True,
            )
            
            # Retry on transient API failures
            if "API" in str(exc) or "rate_limit" in str(exc).lower() or "timeout" in str(exc).lower():
                raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
            
            raise
