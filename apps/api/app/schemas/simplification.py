"""
Simplification Pydantic schemas — LegalLens API
Implements: architecture.md §8 API contracts for /documents/{id}/simplify endpoint.
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


# ── Request schemas ───────────────────────────────────────────────────────────

class SimplifyRequest(BaseModel):
    """Request body for POST /documents/{id}/simplify"""
    
    reading_level: Literal["elementary", "plain_english", "detailed"] = Field(
        default="plain_english",
        description=(
            "Target reading level for simplification. "
            "elementary: 4th-6th grade, plain_english: 8th-10th grade (default), "
            "detailed: 11th-12th grade"
        ),
    )
    
    scope: Literal["full_document"] = Field(
        default="full_document",
        description="Simplification scope. Currently only full_document is supported.",
    )


# ── Response schemas ──────────────────────────────────────────────────────────

class CitationResponse(BaseModel):
    """Citation linking simplified content to source chunks."""
    
    chunk_id: uuid.UUID
    page_number: int | None
    excerpt: str = Field(
        ...,
        description="Brief excerpt from the original source text",
    )


class SimplificationResponse(BaseModel):
    """Response for completed simplification (non-streaming)."""
    
    document_id: uuid.UUID
    simplified_text: str
    reading_level: Literal["elementary", "plain_english", "detailed"]
    citations: list[CitationResponse]
    chunk_count: int
    disclaimer: str = Field(
        default=(
            "This simplified version is for informational purposes only and does not "
            "constitute legal advice. For legal guidance, consult a qualified attorney."
        ),
        description="Mandatory legal disclaimer per architecture.md §3 step 6",
    )


# ── SSE Event schemas ─────────────────────────────────────────────────────────

class SimplificationStreamEvent(BaseModel):
    """
    Server-Sent Event for streaming simplification.
    
    Event types:
    - start: Simplification begun
    - progress: Chunk simplified (map phase)
    - chunk: Simplified chunk content
    - coherence: Coherence pass begun (reduce phase)
    - complete: Final simplified text
    - error: Error occurred
    """
    
    event: Literal["start", "progress", "chunk", "coherence", "complete", "error"]
    data: dict = Field(
        default_factory=dict,
        description="Event-specific data payload",
    )
