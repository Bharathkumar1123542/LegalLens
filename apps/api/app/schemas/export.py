"""
Export Pydantic schemas — LegalLens API
Implements: architecture.md §8 API contracts for export endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


# ── Request schemas ───────────────────────────────────────────────────────────

class CreateExportRequest(BaseModel):
    """Request body for POST /exports"""
    
    export_type: Literal["summary", "checklist", "lawyer_brief", "comparison_report"]
    file_format: Literal["pdf", "docx", "md"] = Field(default="md")
    
    # Exactly one of these must be provided
    document_id: uuid.UUID | None = None
    comparison_job_id: uuid.UUID | None = None
    
    @model_validator(mode="after")
    def check_exactly_one_source(self):
        """Validate exactly one of document_id or comparison_job_id is provided."""
        has_doc = self.document_id is not None
        has_comp = self.comparison_job_id is not None
        
        if has_doc and has_comp:
            raise ValueError("Provide either document_id OR comparison_job_id, not both")
        
        if not has_doc and not has_comp:
            raise ValueError("Must provide either document_id or comparison_job_id")
        
        # Validate export type matches source
        if self.comparison_job_id and self.export_type != "comparison_report":
            raise ValueError(
                "comparison_job_id requires export_type='comparison_report'"
            )
        
        if self.document_id and self.export_type == "comparison_report":
            raise ValueError(
                "export_type='comparison_report' requires comparison_job_id"
            )
        
        return self


# ── Response schemas ──────────────────────────────────────────────────────────

class ExportArtifactResponse(BaseModel):
    """Response for an export artifact."""
    
    id: uuid.UUID
    owner_id: uuid.UUID
    document_id: uuid.UUID | None
    comparison_job_id: uuid.UUID | None
    export_type: Literal["summary", "checklist", "lawyer_brief", "comparison_report"]
    file_format: Literal["pdf", "docx", "md"]
    status: Literal["queued", "generating", "ready", "failed"]
    storage_key: str | None
    created_at: datetime
    download_url: str | None = Field(
        default=None,
        description="Signed S3 URL (populated when status=ready)",
    )
    
    model_config = {"from_attributes": True}


class ExportCreatedResponse(BaseModel):
    """Response for POST /exports"""
    
    export_id: uuid.UUID
    status: str
    message: str = Field(
        default="Export job created",
        description="Status message",
    )
