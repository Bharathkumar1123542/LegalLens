"""
Document ORM model — LegalLens
Implements: architecture.md §7.2 `documents` table schema exactly.
Columns: id, owner_id, original_filename, mime_type, file_size_bytes,
         storage_key, file_hash_sha256, status, processing_stage,
         page_count, language, failure_reason, created_at, updated_at.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger, DateTime, Enum as SAEnum, ForeignKey,
    Integer, String, Text, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


# Enum strings exactly as defined in architecture.md §7.2
DOCUMENT_STATUS = SAEnum(
    "uploaded", "processing", "ready", "failed",
    name="document_status_enum",
)
PROCESSING_STAGE = SAEnum(
    "extracting_text", "ocr", "chunking", "embedding",
    name="processing_stage_enum",
)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    # architecture.md §7.2: mime_type is one of the 3 supported types
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    # architecture.md §7.2: file_size_bytes ≤ 20,971,520 (20 MB)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # S3 object key — format: {owner_id}/{document_id}/{original_filename}
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    # SHA-256 hex string, 64 chars — used for per-user dedup (architecture.md §7.3)
    file_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    status: Mapped[str] = mapped_column(
        DOCUMENT_STATUS, nullable=False, server_default="uploaded",
    )
    processing_stage: Mapped[str | None] = mapped_column(
        PROCESSING_STAGE, nullable=True,
    )
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # BCP-47 language tag (e.g. "en", "fr") — nullable until detected during ingestion
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )

    def __repr__(self) -> str:
        return (
            f"<Document id={self.id} owner={self.owner_id} "
            f"status={self.status!r} file={self.original_filename!r}>"
        )
