"""
Clause Pydantic schemas — LegalLens API
Implements: architecture.md §8 API contracts for /documents/{id}/clauses endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ── Request schemas ───────────────────────────────────────────────────────────

class ExtractClausesRequest(BaseModel):
    """Request body for POST /documents/{id}/extract-clauses"""
    
    clause_types: list[
        Literal[
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
        ]
    ] = Field(
        default=[
            "indemnification",
            "termination",
            "limitation_of_liability",
            "confidentiality",
            "non_compete",
            "arbitration_dispute_resolution",
            "payment_terms",
            "auto_renewal",
            "governing_law",
        ],
        description=(
            "List of clause types to extract. Defaults to all except 'other'. "
            "Extraction runs asynchronously for each type."
        ),
    )


# ── Response schemas ──────────────────────────────────────────────────────────

class ClauseResponse(BaseModel):
    """Response for a single extracted clause."""
    
    id: uuid.UUID
    document_id: uuid.UUID
    source_chunk_id: uuid.UUID | None
    clause_type: Literal[
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
    ]
    text_excerpt: str
    start_offset: int
    end_offset: int
    risk_level: Literal["low", "medium", "high"]
    risk_rationale: str
    created_at: datetime
    
    model_config = {"from_attributes": True}


class ExtractClausesAccepted(BaseModel):
    """202 response for POST /documents/{id}/extract-clauses"""
    
    document_id: uuid.UUID
    clause_types: list[str]
    message: str = Field(
        default="Clause extraction started",
        description="Status message",
    )


class ClausesListResponse(BaseModel):
    """Response for GET /documents/{id}/clauses"""
    
    document_id: uuid.UUID
    clauses: list[ClauseResponse]
    total: int = Field(..., description="Total number of clauses extracted")
    by_type: dict[str, int] = Field(
        default_factory=dict,
        description="Count of clauses by type",
    )
    by_risk: dict[str, int] = Field(
        default_factory=dict,
        description="Count of clauses by risk level",
    )
