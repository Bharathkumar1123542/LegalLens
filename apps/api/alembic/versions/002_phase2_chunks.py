"""
Phase 2 migration — document_chunks table
Implements: architecture.md §7.2 `document_chunks` schema.
Adds: document_chunks table with pgvector embedding column.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector

revision: str = "002_phase2_chunks"
down_revision: str | None = "001_phase1_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── document_chunks ───────────────────────────────────────────────────────
    op.create_table(
        "document_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("page_number", sa.Integer, nullable=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=False),
        # architecture.md §4: Voyage AI voyage-context-4 = 1024 dimensions
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    # Unique constraint: (document_id, chunk_index) — enforces ordering, no duplicates
    op.create_unique_constraint("uq_document_chunks_document_id_chunk_index", "document_chunks", ["document_id", "chunk_index"])


def downgrade() -> None:
    op.drop_table("document_chunks")
