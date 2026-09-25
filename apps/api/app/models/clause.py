"""
Clause ORM model — LegalLens Phase 3
Implements: architecture.md §7.2 `clauses` table schema.
Columns: id, document_id, source_chunk_id, clause_type, text_excerpt,
         start_offset, end_offset, risk_level, risk_rationale, created_at.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime, Enum as SAEnum, ForeignKey,
    Integer, String, Text,
)
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


# Enum strings exactly as defined in architecture.md §7.2
CLAUSE_TYPE = SAEnum(
    "indemnification",
    "termination",
    "limitation_of_liability",
    "confidentiality",
    "non_compete",
    "arbitration_dispute_resolution",
    "payment_terms",
    "auto_renewal",
    "governing_law",
    "other",
    name="clause_type_enum",
)

RISK_LEVEL = SAEnum(
    "low",
    "medium",
    "high",
    name="risk_level_enum",
)


class Clause(Base):
    __tablename__ = "clauses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sql_text("gen_random_uuid()"),
    )
    
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Nullable per architecture.md §7.2: source chunk may not be identifiable
    source_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    clause_type: Mapped[str] = mapped_column(
        CLAUSE_TYPE,
        nullable=False,
        index=True,  # For filtering by clause type
    )
    
    text_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Character offsets within source_chunk_id.text
    # architecture.md §7.2: end_offset > start_offset, both within chunk bounds
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    
    risk_level: Mapped[str] = mapped_column(
        RISK_LEVEL,
        nullable=False,
        index=True,  # For filtering by risk level
    )
    
    # architecture.md §7.2: risk_rationale is 1-2 sentences
    risk_rationale: Mapped[str] = mapped_column(Text, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=sql_text("now()"),
    )

    def __repr__(self) -> str:
        return (
            f"<Clause id={self.id} type={self.clause_type!r} "
            f"risk={self.risk_level!r} doc={self.document_id}>"
        )
