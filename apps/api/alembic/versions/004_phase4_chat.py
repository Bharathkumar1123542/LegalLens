"""
Phase 4 migration — chat_sessions and chat_messages tables
Implements: architecture.md §7.2 chat tables schema.
Adds: chat_sessions, chat_messages with role enum and citations jsonb.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision: str = "004_phase4_chat"
down_revision: str | None = "003_phase3_clauses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Create enum ───────────────────────────────────────────────────────────
    # architecture.md §7.2: message role enum (user, assistant)
    message_role_enum = sa.Enum(
        "user",
        "assistant",
        name="message_role_enum",
    )
    message_role_enum.create(op.get_bind())
    
    # ── chat_sessions table ───────────────────────────────────────────────────
    op.create_table(
        "chat_sessions",
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
            "owner_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "last_message_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    
    # Indexes: document_id for session listing, owner_id for ownership checks
    op.create_index("ix_chat_sessions_document_id", "chat_sessions", ["document_id"])
    op.create_index("ix_chat_sessions_owner_id", "chat_sessions", ["owner_id"])
    
    # ── chat_messages table ───────────────────────────────────────────────────
    op.create_table(
        "chat_messages",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role",
            message_role_enum,
            nullable=False,
        ),
        sa.Column("content", sa.Text, nullable=False),
        # Per architecture.md §7.2: citations jsonb default []
        # Format: [{chunk_id: UUID, page_number: int, excerpt: str}, ...]
        sa.Column(
            "citations",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    
    # Index on session_id for message history retrieval
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])


def downgrade() -> None:
    op.drop_table("chat_messages")
    op.drop_table("chat_sessions")
    
    # Drop enum
    sa.Enum(name="message_role_enum").drop(op.get_bind())
