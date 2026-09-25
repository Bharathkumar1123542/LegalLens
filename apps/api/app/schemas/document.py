"""
Document Pydantic schemas — LegalLens API
Implements: architecture.md §8 API contracts for /documents/* endpoints.
architecture.md §7.3: monetary/date values in text_excerpt stored as original source text —
  displayed as-is, never parsed/normalised here.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ── Document response ─────────────────────────────────────────────────────────

DocumentStatus = Literal["uploaded", "processing", "ready", "failed"]
ProcessingStage = Literal["extracting_text", "ocr", "chunking", "embedding"]


class DocumentResponse(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    original_filename: str
    mime_type: str
    file_size_bytes: int
    file_hash_sha256: str
    status: DocumentStatus
    processing_stage: ProcessingStage | None = None
    page_count: int | None = None
    language: str | None = None
    failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentStatusResponse(BaseModel):
    """Lightweight polling response — avoids returning full doc metadata on every poll."""
    id: uuid.UUID
    status: DocumentStatus
    processing_stage: ProcessingStage | None = None
    failure_reason: str | None = None

    model_config = {"from_attributes": True}


class UploadAccepted(BaseModel):
    """202 response for POST /documents — full document row after creation."""
    id: uuid.UUID
    status: DocumentStatus
    original_filename: str
    file_size_bytes: int
    created_at: datetime

    model_config = {"from_attributes": True}
