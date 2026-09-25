"""
Phase 5 migration — comparison and export tables
Implements: architecture.md §7.2 comparison_jobs, comparison_results, export_artifacts.
Adds: comparison tables with clause alignment, export artifacts with format options.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "005_phase5_comparison_export"
down_revision: str | None = "004_phase4_chat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Create enums ──────────────────────────────────────────────────────────
    # Job status enum (shared by comparison_jobs)
    job_status_enum = sa.Enum(
        "queued",
        "running",
        "completed",
        "failed",
        name="job_status_enum",
    )
    job_status_enum.create(op.get_bind())
    
    # Materiality enum for comparison results
    materiality_enum = sa.Enum(
        "none",
        "minor",
        "significant",
        "critical",
        name="materiality_enum",
    )
    materiality_enum.create(op.get_bind())
    
    # Export type enum
    export_type_enum = sa.Enum(
        "summary",
        "checklist",
        "lawyer_brief",
        "comparison_report",
        name="export_type_enum",
    )
    export_type_enum.create(op.get_bind())
    
    # File format enum
    file_format_enum = sa.Enum(
        "pdf",
        "docx",
        "md",
        name="file_format_enum",
    )
    file_format_enum.create(op.get_bind())
    
    # Export status enum
    export_status_enum = sa.Enum(
        "queued",
        "generating",
        "ready",
        "failed",
        name="export_status_enum",
    )
    export_status_enum.create(op.get_bind())
    
    # ── comparison_jobs table ─────────────────────────────────────────────────
    op.create_table(
        "comparison_jobs",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "owner_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            job_status_enum,
            nullable=False,
            server_default="queued",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    
    op.create_index("ix_comparison_jobs_owner_id", "comparison_jobs", ["owner_id"])
    
    # ── comparison_job_documents table (join) ─────────────────────────────────
    # Per architecture.md §7.2: composite PK (comparison_job_id + document_id)
    # 2-5 documents per job enforced at service layer
    op.create_table(
        "comparison_job_documents",
        sa.Column(
            "comparison_job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("comparison_jobs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "document_order",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )
    
    # ── comparison_results table ──────────────────────────────────────────────
    op.create_table(
        "comparison_results",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "comparison_job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("comparison_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("clause_type", sa.Text, nullable=False),
        # Per architecture.md §7.2: excerpts_by_document jsonb {document_id: excerpt_text}
        sa.Column("excerpts_by_document", JSONB, nullable=False),
        sa.Column("diff_summary", sa.Text, nullable=False),
        sa.Column(
            "materiality",
            materiality_enum,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    
    op.create_index("ix_comparison_results_comparison_job_id", "comparison_results", ["comparison_job_id"])
    
    # ── export_artifacts table ────────────────────────────────────────────────
    op.create_table(
        "export_artifacts",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "owner_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "comparison_job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("comparison_jobs.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "export_type",
            export_type_enum,
            nullable=False,
        ),
        sa.Column(
            "file_format",
            file_format_enum,
            nullable=False,
        ),
        sa.Column(
            "status",
            export_status_enum,
            nullable=False,
            server_default="queued",
        ),
        sa.Column("storage_key", sa.String(1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    
    op.create_index("ix_export_artifacts_owner_id", "export_artifacts", ["owner_id"])
    
    # Per architecture.md §7.2: exactly one of document_id or comparison_job_id must be non-null
    op.create_check_constraint(
        "ck_export_artifacts_exactly_one_source",
        "export_artifacts",
        "(document_id IS NOT NULL AND comparison_job_id IS NULL) OR "
        "(document_id IS NULL AND comparison_job_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_table("export_artifacts")
    op.drop_table("comparison_results")
    op.drop_table("comparison_job_documents")
    op.drop_table("comparison_jobs")
    
    # Drop enums
    sa.Enum(name="export_status_enum").drop(op.get_bind())
    sa.Enum(name="file_format_enum").drop(op.get_bind())
    sa.Enum(name="export_type_enum").drop(op.get_bind())
    sa.Enum(name="materiality_enum").drop(op.get_bind())
    sa.Enum(name="job_status_enum").drop(op.get_bind())
