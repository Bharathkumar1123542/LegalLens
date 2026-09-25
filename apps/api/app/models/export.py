"""
Export ORM model — LegalLens Phase 5
Implements: architecture.md §7.2 export_artifacts table.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime, Enum as SAEnum, ForeignKey, String, CheckConstraint,
)
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


# Enums per architecture.md §7.2
EXPORT_TYPE = SAEnum(
    "summary",
    "checklist",
    "lawyer_brief",
    "comparison_report",
    name="export_type_enum",
)

FILE_FORMAT = SAEnum(
    "pdf",
    "docx",
    "md",
    name="file_format_enum",
)

EXPORT_STATUS = SAEnum(
    "queued",
    "generating",
    "ready",
    "failed",
    name="export_status_enum",
)


class ExportArtifact(Base):
    """
    Export artifact (PDF, DOCX, or Markdown).
    
    Per architecture.md §7.2:
    - id PK, owner_id FK
    - document_id FK nullable OR comparison_job_id FK nullable
      (exactly one non-null)
    - export_type enum(summary/checklist/lawyer_brief/comparison_report)
    - file_format enum(pdf/docx/md)
    - status enum(queued/generating/ready/failed)
    - storage_key nullable until ready
    - created_at
    """
    __tablename__ = "export_artifacts"
    
    # Add table-level check constraint: exactly one of document_id or comparison_job_id must be non-null
    __table_args__ = (
        CheckConstraint(
            "(document_id IS NOT NULL AND comparison_job_id IS NULL) OR "
            "(document_id IS NULL AND comparison_job_id IS NOT NULL)",
            name="ck_export_artifacts_exactly_one_source",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sql_text("gen_random_uuid()"),
    )
    
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Exactly one of these two must be non-null (enforced by CHECK constraint)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=True,
    )
    
    comparison_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comparison_jobs.id", ondelete="CASCADE"),
        nullable=True,
    )
    
    export_type: Mapped[str] = mapped_column(
        EXPORT_TYPE,
        nullable=False,
    )
    
    file_format: Mapped[str] = mapped_column(
        FILE_FORMAT,
        nullable=False,
    )
    
    status: Mapped[str] = mapped_column(
        EXPORT_STATUS,
        nullable=False,
        server_default="queued",
    )
    
    # S3 object key (nullable until status=ready)
    storage_key: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=sql_text("now()"),
    )

    def __repr__(self) -> str:
        return (
            f"<ExportArtifact id={self.id} type={self.export_type!r} "
            f"format={self.file_format!r} status={self.status!r}>"
        )
