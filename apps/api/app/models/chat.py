"""
Chat ORM models — LegalLens Phase 4
Implements: architecture.md §7.2 chat_sessions and chat_messages tables.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime, Enum as SAEnum, ForeignKey, Text,
)
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


# Enum for message role per architecture.md §7.2
MESSAGE_ROLE = SAEnum(
    "user",
    "assistant",
    name="message_role_enum",
)


class ChatSession(Base):
    """
    Chat session scoped to a single document.
    
    Per architecture.md §7.2:
    - id PK, document_id FK, owner_id FK
    - created_at, last_message_at
    """
    __tablename__ = "chat_sessions"

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
    
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=sql_text("now()"),
    )
    
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=sql_text("now()"),
    )

    def __repr__(self) -> str:
        return (
            f"<ChatSession id={self.id} doc={self.document_id} "
            f"owner={self.owner_id}>"
        )


class ChatMessage(Base):
    """
    Chat message with role (user/assistant) and citations.
    
    Per architecture.md §7.2:
    - id PK, session_id FK, role enum(user, assistant), content
    - citations jsonb default [] (required non-empty when role=assistant
      and answer makes factual claim)
    - citations format: [{chunk_id, page_number, excerpt}, ...]
    - created_at
    """
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sql_text("gen_random_uuid()"),
    )
    
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    role: Mapped[str] = mapped_column(
        MESSAGE_ROLE,
        nullable=False,
    )
    
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Per architecture.md §7.2:
    # citations jsonb default []
    # Format: [{chunk_id: UUID, page_number: int, excerpt: str}, ...]
    # Required non-empty when role=assistant and answer makes factual claim
    citations: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sql_text("'[]'::jsonb"),
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=sql_text("now()"),
    )

    def __repr__(self) -> str:
        return (
            f"<ChatMessage id={self.id} session={self.session_id} "
            f"role={self.role!r}>"
        )
