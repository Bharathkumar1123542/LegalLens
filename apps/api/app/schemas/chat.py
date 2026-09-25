"""
Chat Pydantic schemas — LegalLens API
Implements: architecture.md §8 API contracts for chat endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ── Request schemas ───────────────────────────────────────────────────────────

class StartChatRequest(BaseModel):
    """Request body for POST /documents/{id}/chat/sessions (empty body for now)"""
    pass


class AskQuestionRequest(BaseModel):
    """Request body for POST /chat/sessions/{id}/messages"""
    
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User's question about the document",
    )
    
    top_k: int = Field(
        default=8,
        ge=1,
        le=20,
        description="Number of relevant chunks to retrieve (default: 8)",
    )


# ── Response schemas ──────────────────────────────────────────────────────────

class CitationResponse(BaseModel):
    """Citation to a source chunk."""
    
    chunk_id: uuid.UUID
    page_number: int | None
    excerpt: str = Field(..., description="Excerpt from the source chunk")


class ChatMessageResponse(BaseModel):
    """Response for a single chat message."""
    
    id: uuid.UUID
    session_id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    citations: list[CitationResponse] = Field(
        default_factory=list,
        description=(
            "Citations for assistant messages. Per architecture.md §7.2, "
            "required non-empty when role=assistant and answer makes factual claim."
        ),
    )
    created_at: datetime
    
    model_config = {"from_attributes": True}
    
    @classmethod
    def from_orm_with_citations(cls, message) -> "ChatMessageResponse":
        """
        Convert ORM ChatMessage to response schema.
        
        Handles citations conversion from JSONB dict to CitationResponse list.
        """
        # Convert citations from dict to CitationResponse objects
        citations = []
        if message.citations and isinstance(message.citations, list):
            for citation_dict in message.citations:
                citations.append(
                    CitationResponse(
                        chunk_id=uuid.UUID(citation_dict["chunk_id"]),
                        page_number=citation_dict.get("page_number"),
                        excerpt=citation_dict.get("excerpt", ""),
                    )
                )
        
        return cls(
            id=message.id,
            session_id=message.session_id,
            role=message.role,
            content=message.content,
            citations=citations,
            created_at=message.created_at,
        )


class ChatSessionResponse(BaseModel):
    """Response for a chat session."""
    
    id: uuid.UUID
    document_id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    last_message_at: datetime
    message_count: int | None = Field(
        default=None,
        description="Total number of messages in session (optional)",
    )
    
    model_config = {"from_attributes": True}


class ChatSessionCreatedResponse(BaseModel):
    """Response for POST /documents/{id}/chat/sessions"""
    
    session: ChatSessionResponse
    message: str = Field(
        default="Chat session created",
        description="Status message",
    )


class ChatHistoryResponse(BaseModel):
    """Response for GET /chat/sessions/{id}/messages"""
    
    session_id: uuid.UUID
    messages: list[ChatMessageResponse]
    total: int = Field(..., description="Total number of messages in session")
    page: int | None = Field(
        default=None,
        description="Current page number (if paginated)",
    )
    page_size: int | None = Field(
        default=None,
        description="Number of messages per page (if paginated)",
    )


class ChatSessionListResponse(BaseModel):
    """Response for GET /documents/{id}/chat/sessions"""
    
    document_id: uuid.UUID
    sessions: list[ChatSessionResponse]
    total: int = Field(..., description="Total number of sessions for document")
