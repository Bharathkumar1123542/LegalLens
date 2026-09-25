"""
DocumentChunk ORM model — LegalLens
Implements: architecture.md §7.2 `document_chunks` table.
Columns: id, document_id, chunk_index, page_number, text, token_count,
         embedding (pgvector), created_at.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.db.base import Base


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

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
    # 0-indexed, unique per document — enforces ordering
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # Nullable: plain text files have no page concept
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # architecture.md §7.2: ≤500 tokens target, 700 hard cap
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # architecture.md §4: Voyage AI voyage-context-4 produces 1024-dim vectors
    # Nullable until embedding step completes (architecture.md §3 step 3)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1024),
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
            f"<DocumentChunk doc={self.document_id} idx={self.chunk_index} "
            f"tokens={self.token_count}>"
        )
