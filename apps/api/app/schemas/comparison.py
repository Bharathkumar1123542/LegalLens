"""
Comparison Pydantic schemas — LegalLens API
Implements: architecture.md §8 API contracts for comparison endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ── Request schemas ───────────────────────────────────────────────────────────

class CreateComparisonRequest(BaseModel):
    """Request body for POST /comparisons"""
    
    document_ids: list[uuid.UUID] = Field(
        ...,
        min_length=2,
        max_length=5,
        description="2-5 document UUIDs to compare (all must be ready)",
    )


# ── Response schemas ──────────────────────────────────────────────────────────

class ComparisonResultResponse(BaseModel):
    """Response for a single comparison result."""
    
    id: uuid.UUID
    clause_type: str
    excerpts_by_document: dict[str, str] = Field(
        ...,
        description="Map of document_id to excerpt text",
    )
    diff_summary: str
    materiality: Literal["none", "minor", "significant", "critical"]
    created_at: datetime
    
    model_config = {"from_attributes": True}


class ComparisonJobResponse(BaseModel):
    """Response for a comparison job."""
    
    id: uuid.UUID
    owner_id: uuid.UUID
    status: Literal["queued", "running", "completed", "failed"]
    created_at: datetime
    completed_at: datetime | None
    results: list[ComparisonResultResponse] = Field(
        default_factory=list,
        description="Comparison results (populated when status=completed)",
    )
    
    model_config = {"from_attributes": True}


class ComparisonJobCreatedResponse(BaseModel):
    """Response for POST /comparisons"""
    
    comparison_job_id: uuid.UUID
    status: str
    message: str = Field(
        default="Comparison job created",
        description="Status message",
    )
