"""
Initial migration — Phase 1: users, documents, audit_logs tables.
Implements: architecture.md §7.2 schema definitions exactly.
code-standards.md §Security: REVOKE UPDATE/DELETE on audit_logs from the app role.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET

revision: str = "001_phase1_initial"
down_revision: str | None = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enable pgcrypto for gen_random_uuid() ────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── Enums ─────────────────────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE user_role_enum AS ENUM ('user', 'admin');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE document_status_enum AS ENUM (
                'uploaded', 'processing', 'ready', 'failed'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE processing_stage_enum AS ENUM (
                'extracting_text', 'ocr', 'chunking', 'embedding'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("user", "admin", name="user_role_enum", create_type=False), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── documents ─────────────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger, nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("file_hash_sha256", sa.String(64), nullable=False),
        sa.Column(
            "status",
            sa.Enum("uploaded", "processing", "ready", "failed", name="document_status_enum", create_type=False),
            nullable=False,
            server_default="uploaded",
        ),
        sa.Column(
            "processing_stage",
            sa.Enum("extracting_text", "ocr", "chunking", "embedding", name="processing_stage_enum", create_type=False),
            nullable=True,
        ),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("language", sa.String(16), nullable=True),
        sa.Column("failure_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_documents_owner_id", "documents", ["owner_id"])
    # Per-user dedup index — architecture.md §7.3
    op.create_index("ix_documents_owner_hash", "documents", ["owner_id", "file_hash_sha256"])

    # ── audit_logs (append-only) ──────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("actor_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", UUID(as_uuid=True), nullable=False),
        sa.Column("metadata", JSONB, nullable=False, server_default="'{}'"),
        sa.Column("ip_address", INET, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_resource_id", "audit_logs", ["resource_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])

    # ── Audit-log append-only enforcement ─────────────────────────────────────
    # code-standards.md §Security: "application DB role must have no UPDATE/DELETE
    # grant on audit_logs". The application connects as 'legallens_app' (see docker-compose).
    # This REVOKE is idempotent — safe to re-run.
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'legallens_app') THEN
                REVOKE UPDATE, DELETE ON audit_logs FROM legallens_app;
            END IF;
        END $$
    """)

    # ── updated_at auto-update trigger for users and documents ───────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    for table in ("users", "documents"):
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION update_updated_at()
        """)


def downgrade() -> None:
    for table in ("users", "documents"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at")

    op.drop_table("audit_logs")
    op.drop_table("documents")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS processing_stage_enum")
    op.execute("DROP TYPE IF EXISTS document_status_enum")
    op.execute("DROP TYPE IF EXISTS user_role_enum")
