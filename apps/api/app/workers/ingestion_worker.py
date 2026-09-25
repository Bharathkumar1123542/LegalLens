"""
Ingestion Worker — LegalLens Phase 2
Implements: architecture.md §3 steps 2-3 (text extraction → OCR → chunking → embedding).
Status transitions: uploaded → processing → ready/failed
Processing stages: extracting_text → ocr → chunking → embedding
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select

from app.workers import celery_app, AsyncTask
from app.core.config import settings
from app.db.session import get_async_session
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.text_extraction import (
    extract_text_from_pdf,
    extract_text_from_docx,
    extract_text_from_plain,
    detect_scanned_pdf_pages,
)
from app.services.ocr import ocr_pdf_page
from app.services.chunking import chunk_text
from app.services.embedding import embed_chunks
from app.services.storage import _s3_client
from app.services.audit import record_audit_event

log = structlog.get_logger(__name__)


@celery_app.task(name="process_document", base=AsyncTask, bind=True, max_retries=3)
async def process_document_task(self, document_id: str) -> None:
    """
    Process a document through the full ingestion pipeline.
    
    Steps (architecture.md §3):
      1. Extract text (or OCR for scanned pages)
      2. Chunk text
      3. Embed chunks
      4. Update status to 'ready' or 'failed'
    
    Status transitions:
      uploaded → processing (stage: extracting_text)
                → processing (stage: ocr) [if scanned pages detected]
                → processing (stage: chunking)
                → processing (stage: embedding)
                → ready [or failed with failure_reason]
    """
    doc_uuid = uuid.UUID(document_id)
    
    async with get_async_session() as db:
        try:
            # Fetch document
            result = await db.execute(select(Document).where(Document.id == doc_uuid))
            doc: Document | None = result.scalar_one_or_none()
            
            if not doc:
                log.error("ingestion.document_not_found", document_id=document_id)
                return
            
            # Update status to processing
            doc.status = "processing"
            doc.processing_stage = "extracting_text"
            await db.commit()
            
            # Step 1: Fetch raw file from S3
            s3 = _s3_client()
            response = s3.get_object(Bucket=settings.S3_BUCKET, Key=doc.storage_key)
            raw_bytes = response["Body"].read()
            
            # Step 2: Extract text based on MIME type
            if doc.mime_type == "application/pdf":
                pages = extract_text_from_pdf(raw_bytes)
                
                # Check for scanned pages
                scanned_page_numbers = detect_scanned_pdf_pages(pages)
                
                if scanned_page_numbers:
                    doc.processing_stage = "ocr"
                    await db.commit()
                    
                    # OCR scanned pages
                    for page_num in scanned_page_numbers:
                        ocr_text = ocr_pdf_page(raw_bytes, page_num)
                        # Replace empty text with OCR result
                        pages[page_num - 1]["text"] = ocr_text
                        pages[page_num - 1]["needs_ocr"] = False
                
                # Combine all pages
                full_text = "\n\n".join(p["text"] for p in pages)
                doc.page_count = len(pages)
                
            elif doc.mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                full_text = extract_text_from_docx(raw_bytes)
                doc.page_count = None  # DOCX has no page concept
                
            elif doc.mime_type == "text/plain":
                full_text = extract_text_from_plain(raw_bytes)
                doc.page_count = None
                
            else:
                raise ValueError(f"Unsupported MIME type: {doc.mime_type}")
            
            # Step 3: Chunk text
            doc.processing_stage = "chunking"
            await db.commit()
            
            if doc.mime_type == "application/pdf":
                # Chunk each page separately for PDFs
                all_chunks = []
                global_chunk_index = 0
                for page_info in pages:
                    page_chunks = chunk_text(page_info["text"], page_info["page_number"])
                    for chunk_dict in page_chunks:
                        chunk_dict["chunk_index"] = global_chunk_index
                        global_chunk_index += 1
                    all_chunks.extend(page_chunks)
            else:
                # Single-pass chunking for DOCX/TXT
                all_chunks = chunk_text(full_text, page_number=None)
            
            # Create DocumentChunk rows
            for chunk_dict in all_chunks:
                chunk = DocumentChunk(
                    id=uuid.uuid4(),
                    document_id=doc_uuid,
                    chunk_index=chunk_dict["chunk_index"],
                    page_number=chunk_dict["page_number"],
                    text=chunk_dict["text"],
                    token_count=chunk_dict["token_count"],
                    embedding=None,  # Populated in next step
                )
                db.add(chunk)
            
            await db.commit()
            
            log.info(
                "ingestion.chunks_created",
                document_id=document_id,
                chunk_count=len(all_chunks),
            )
            
            # Step 4: Embed chunks
            doc.processing_stage = "embedding"
            await db.commit()
            
            await embed_chunks(db=db, document_id=doc_uuid)
            
            # Step 5: Mark as ready
            doc.status = "ready"
            doc.processing_stage = None
            await db.commit()
            
            # Audit log
            await record_audit_event(
                db=db,
                actor_id=None,  # System action
                action="document.processing_completed",
                resource_type="document",
                resource_id=doc_uuid,
                metadata={
                    "chunk_count": len(all_chunks),
                    "page_count": doc.page_count,
                },
                ip_address="system",
            )
            
            log.info(
                "ingestion.completed",
                document_id=document_id,
                chunk_count=len(all_chunks),
            )
            
        except Exception as exc:
            log.error(
                "ingestion.failed",
                document_id=document_id,
                error=str(exc),
                exc_info=True,
            )
            
            # Mark as failed
            async with get_async_session() as db:
                result = await db.execute(select(Document).where(Document.id == doc_uuid))
                doc = result.scalar_one_or_none()
                if doc:
                    doc.status = "failed"
                    doc.failure_reason = str(exc)[:500]  # Truncate if too long
                    await db.commit()
            
            # Retry on transient failures
            if "API" in str(exc) or "timeout" in str(exc).lower():
                raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))
            
            raise
