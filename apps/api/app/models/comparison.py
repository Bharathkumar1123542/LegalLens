"""
Comparison ORM models — LegalLens Phase 5
Implements: architecture.md §7.2 comparison tables.
Models: ComparisonJob, ComparisonJobDocument (join), ComparisonResult
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime, Enum as SAEnum, ForeignKey, Integer, Text,
    UniqueConstraint,
)
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


# Enums per architecture.md §7.2
JOB_STATUS = SAEnum(
    "queued",
    "running",
    "completed",
    "failed",
    name="job_status_enum",
)

MATERIALITY = SAEnum(
    "none",
    "minor",
    "significant",
    "critical",
    name="materiality_enum",
)


class ComparisonJob(Base):
    """
    Comparison job for clause-aligned diff across 2-5 documents.
    
    Per architecture.md §7.2:
    - id PK, owner_id FK, status enum(queued/running/completed/failed)
    - created_at, completed_at (nullable until terminal)
    """
    __tablename__ = "comparison_jobs"

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
    
    status: Mapped[str] = mapped_column(
        JOB_STATUS,
        nullable=False,
        server_default="queued",
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=sql_text("now()"),
    )
    
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<ComparisonJob id={self.id} owner={self.owner_id} "
            f"status={self.status!r}>"
        )


class ComparisonJobDocument(Base):
    """
    Join table: documents included in a comparison job.
    
    Per architecture.md §7.2:
    - Composite PK (comparison_job_id + document_id)
    - 2 ≤ rows per job ≤ 5 (enforced at service layer)
    """
    __tablename__ = "comparison_job_documents"

    comparison_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comparison_jobs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    
    # Optional: order for display (0-indexed)
    document_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    def __repr__(self) -> str:
        return (
            f"<ComparisonJobDocument job={self.comparison_job_id} "
            f"doc={self.document_id}>"
        )


class ComparisonResult(Base):
    """
    Clause-aligned comparison result with materiality rating.
    
    Per architecture.md §7.2:
    - id PK, comparison_job_id FK, clause_type
    - excerpts_by_document jsonb {document_id: excerpt_text}
    - diff_summary, materiality enum(none/minor/significant/critical)
    - created_at
    """
    __tablename__ = "comparison_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sql_text("gen_random_uuid()"),
    )
    
    comparison_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comparison_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Clause type being compared (from clause_type_enum)
    clause_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    
    # Per architecture.md §7.2:
    # excerpts_by_document jsonb: {document_id: excerpt_text}
    excerpts_by_document: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )
    
    diff_summary: Mapped[str] = mapped_column(Text, nullable=False)
    
    materiality: Mapped[str] = mapped_column(
        MATERIALITY,
        nullable=False,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=sql_text("now()"),
    )

    def __repr__(self) -> str:
        return (
            f"<ComparisonResult id={self.id} type={self.clause_type!r} "
            f"materiality={self.materiality!r}>"
        )
