"""
Document Ingestion Service — LegalLens (Phase 1 slice)
Implements: architecture.md §6.2 Document Ingestion Module (Phase 1 scope only).
  - create_document(): validate, deduplicate, store to S3, create DB row (status=uploaded), enqueue
  - process_document(): stub — full implementation in Phase 2 (text extraction, OCR, chunking)

Phase 1 exit criterion (ai-workflow-rules.md): user uploads a file → status=uploaded.
Phase 2 will implement the Celery worker that transitions status to processing→ready/failed.

code-standards.md §Security:
  - Files validated by magic-byte inspection, NOT extension
  - Duplicate upload (same hash, same owner) → return existing Document, do not reprocess
  - Size capped at MAX_UPLOAD_SIZE_MB (validated at gateway before this function is called,
    but double-checked here per defence-in-depth)
"""

from __future__ import annotations

import hashlib
import io
import uuid

import structlog
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import Document
from app.services.storage import upload_to_s3
from app.services.audit import record_audit_event

log = structlog.get_logger(__name__)

# architecture.md §7.3: accepted MIME types (magic-byte check is authoritative)
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}

# Magic-byte signatures for server-side validation (not extension-based)
# code-standards.md: "uploaded files validated by magic-byte inspection, not extension"
_MAGIC_SIGNATURES: dict[bytes, str] = {
    b"\x25\x50\x44\x46": "application/pdf",           # PDF: %PDF
    b"\x50\x4B\x03\x04": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # DOCX (ZIP)
}

_MAX_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


def _detect_mime_type(header: bytes) -> str | None:
    """
    Detect MIME type from the first bytes of the file.
    Plain text has no universal magic bytes — falls back to checking
    that all bytes are valid UTF-8 text (no NUL bytes, decodable).
    Returns the MIME type string, or None if unsupported.
    """
    for magic, mime in _MAGIC_SIGNATURES.items():
        if header.startswith(magic):
            return mime
    # Plain text fallback: must be decodable UTF-8 with no binary markers
    try:
        header.decode("utf-8")
        if b"\x00" not in header:  # NUL bytes indicate binary
            return "text/plain"
    except UnicodeDecodeError:
        pass
    return None


async def create_document(
    owner_id: uuid.UUID,
    file: UploadFile,
    db: AsyncSession,
    ip_address: str = "unknown",
) -> Document:
    """
    Phase 1 ingestion entry point (sync path):
      1. Read file bytes (defence-in-depth size check)
      2. Magic-byte MIME validation
      3. Compute SHA-256 for deduplication
      4. Return existing Document if same hash+owner already exists
      5. Upload to S3/MinIO
      6. Create Document row (status=uploaded)
      7. Enqueue processing job (Celery — worker implemented in Phase 2)
      8. Write audit log row

    Returns the Document ORM object (status=uploaded).
    """
    # ── 1. Read file ──────────────────────────────────────────────────────────
    raw_bytes = await file.read()

    # Defence-in-depth size check (proxy should already reject >20 MB)
    if len(raw_bytes) > _MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB} MB limit.",
        )

    if len(raw_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # ── 2. Magic-byte MIME detection ─────────────────────────────────────────
    detected_mime = _detect_mime_type(raw_bytes[:16])
    if detected_mime is None or detected_mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unsupported file type. Accepted: PDF, DOCX, plain text. "
                "Validation is based on file content, not the filename extension."
            ),
        )

    # ── 3. SHA-256 for deduplication ─────────────────────────────────────────
    file_hash = hashlib.sha256(raw_bytes).hexdigest()

    # ── 4. Deduplication check (per-owner) ───────────────────────────────────
    # architecture.md §7.3: "return existing Document instead of reprocessing if
    # file_hash_sha256 already exists for the same owner"
    existing_result = await db.execute(
        select(Document).where(
            and_(
                Document.owner_id == owner_id,
                Document.file_hash_sha256 == file_hash,
            )
        )
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        log.info(
            "document.deduplicated",
            owner_id=str(owner_id),
            document_id=str(existing.id),
        )
        return existing

    # ── 5. Upload to S3/MinIO ─────────────────────────────────────────────────
    doc_id = uuid.uuid4()
    # Safe filename: strip path components
    safe_name = (file.filename or "upload").split("/")[-1].split("\\")[-1]
    storage_key = f"{owner_id}/{doc_id}/{safe_name}"

    await upload_to_s3(
        key=storage_key,
        data=io.BytesIO(raw_bytes),
        content_type=detected_mime,
    )

    # ── 6. Create Document row ────────────────────────────────────────────────
    document = Document(
        id=doc_id,
        owner_id=owner_id,
        original_filename=safe_name,
        mime_type=detected_mime,
        file_size_bytes=len(raw_bytes),
        storage_key=storage_key,
        file_hash_sha256=file_hash,
        status="uploaded",
        processing_stage=None,
    )
    db.add(document)
    await db.flush()

    # ── 7. Enqueue processing job ─────────────────────────────────────────────
    # Phase 2 will replace this stub with a real Celery task
    _enqueue_processing_stub(str(doc_id))

    # ── 8. Audit log ─────────────────────────────────────────────────────────
    await record_audit_event(
        db=db,
        actor_id=owner_id,
        action="document.upload",
        resource_type="document",
        resource_id=doc_id,
        metadata={
            "mime_type": detected_mime,
            "file_size_bytes": len(raw_bytes),
            "original_filename": safe_name,
        },
        ip_address=ip_address,
    )

    log.info(
        "document.uploaded",
        owner_id=str(owner_id),
        document_id=str(doc_id),
        mime_type=detected_mime,
        size=len(raw_bytes),
    )
    return document


def _enqueue_processing_stub(document_id: str) -> None:
    """
    Enqueue document processing task.
    Phase 2: delegates to Celery worker for async processing pipeline.
    """
    try:
        from app.workers.ingestion_worker import process_document_task
        task = process_document_task.delay(document_id)
        log.info("document.processing_queued", document_id=document_id, task_id=task.id)
    except Exception as exc:
        # If Celery is unavailable, log but don't fail the upload
        log.error("document.enqueue_failed", document_id=document_id, error=str(exc))
