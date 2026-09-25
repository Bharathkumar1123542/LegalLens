"""
Phase 3 migration — clauses table
Implements: architecture.md §7.2 `clauses` schema.
Adds: clauses table with clause_type and risk_level enums.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "003_phase3_clauses"
down_revision: str | None = "002_phase2_chunks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Create enums ──────────────────────────────────────────────────────────
    # architecture.md §7.2: clause_type enum with 10 values
    clause_type_enum = sa.Enum(
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
    clause_type_enum.create(op.get_bind())
    
    # architecture.md §7.2: risk_level enum with 3 values
    risk_level_enum = sa.Enum(
        "low",
        "medium",
        "high",
        name="risk_level_enum",
    )
    risk_level_enum.create(op.get_bind())
    
    # ── clauses table ─────────────────────────────────────────────────────────
    op.create_table(
        "clauses",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_chunk_id",
            UUID(as_uuid=True),
            sa.ForeignKey("document_chunks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "clause_type",
            clause_type_enum,
            nullable=False,
        ),
        sa.Column("text_excerpt", sa.Text, nullable=False),
        sa.Column("start_offset", sa.Integer, nullable=False),
        sa.Column("end_offset", sa.Integer, nullable=False),
        sa.Column(
            "risk_level",
            risk_level_enum,
            nullable=False,
        ),
        sa.Column("risk_rationale", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    
    # Indexes per architecture.md: document_id for ownership queries,
    # clause_type and risk_level for filtering
    op.create_index("ix_clauses_document_id", "clauses", ["document_id"])
    op.create_index("ix_clauses_clause_type", "clauses", ["clause_type"])
    op.create_index("ix_clauses_risk_level", "clauses", ["risk_level"])
    
    # Constraint: end_offset must be > start_offset (architecture.md §7.2)
    op.create_check_constraint(
        "ck_clauses_offsets",
        "clauses",
        "end_offset > start_offset",
    )


def downgrade() -> None:
    op.drop_table("clauses")
    
    # Drop enums
    sa.Enum(name="risk_level_enum").drop(op.get_bind())
    sa.Enum(name="clause_type_enum").drop(op.get_bind())
