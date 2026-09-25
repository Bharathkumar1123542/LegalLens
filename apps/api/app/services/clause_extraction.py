"""
Clause Extraction Service — LegalLens
Implements: architecture.md §6.5 Clause & Risk Extraction Service.
Responsibility: Hybrid rule-based + LLM clause tagging and risk scoring.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_chunk import DocumentChunk
from app.services.llm_orchestration import generate_grounded_response

logger = logging.getLogger(__name__)


# ── Data Models ───────────────────────────────────────────────────────────────


class ClauseCandidate(BaseModel):
    """Extracted clause with risk assessment."""
    
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
    start_offset: int = Field(..., ge=0)
    end_offset: int = Field(..., gt=0)
    chunk_id: uuid.UUID
    risk_level: Literal["low", "medium", "high"]
    risk_rationale: str = Field(..., min_length=1)
    
    @field_validator("end_offset")
    @classmethod
    def validate_offsets(cls, v: int, info) -> int:
        """Ensure end_offset > start_offset."""
        if "start_offset" in info.data and v <= info.data["start_offset"]:
            raise ValueError("end_offset must be greater than start_offset")
        return v


# ── Keyword Pre-filtering ─────────────────────────────────────────────────────


# Per architecture.md §6.5: regex/keyword pre-filter narrows candidate chunks
# before LLM classification, reducing claude-haiku calls per document.
CLAUSE_TYPE_KEYWORDS = {
    "indemnification": [
        "indemnif",
        "indemnit",
        "hold harmless",
        "hold the",
        "defend",
    ],
    "termination": [
        "terminat",
        "cancel",
        "end this agreement",
        "expire",
        "discontinue",
    ],
    "limitation_of_liability": [
        "limit",
        "liability",
        "liable",
        "consequential damages",
        "indirect damages",
        "cap",
    ],
    "confidentiality": [
        "confidential",
        "proprietary",
        "non-disclosure",
        "nda",
        "secret",
    ],
    "non_compete": [
        "non-compete",
        "noncompete",
        "compete",
        "competitive",
        "solicit",
        "non-solicitation",
    ],
    "arbitration_dispute_resolution": [
        "arbitrat",
        "mediat",
        "dispute resolution",
        "litigation",
        "forum",
        "jurisdiction",
    ],
    "payment_terms": [
        "payment",
        "pay",
        "invoice",
        "fee",
        "price",
        "compensat",
        "due",
    ],
    "auto_renewal": [
        "renew",
        "auto",
        "automatic",
        "extend",
        "term",
        "evergreen",
    ],
    "governing_law": [
        "governing law",
        "governed by",
        "applicable law",
        "jurisdiction",
        "venue",
    ],
    "other": [
        # Catch-all for significant clauses not in other categories
        "obligat",
        "right",
        "severab",
        "entire agreement",
        "amendment",
        "waiver",
        "notice",
    ],
}


def filter_chunks_by_keywords(
    chunks: list[DocumentChunk],
    clause_type: str,
) -> list[DocumentChunk]:
    """
    Pre-filter chunks using keyword matching before LLM classification.
    
    Per architecture.md §6.5: reduces LLM calls by only sending relevant chunks.
    
    Args:
        chunks: All document chunks
        clause_type: Type of clause to filter for
    
    Returns:
        List of chunks that match keywords for the clause type
    """
    keywords = CLAUSE_TYPE_KEYWORDS.get(clause_type, [])
    if not keywords:
        logger.warning(f"No keywords defined for clause type: {clause_type}")
        return []
    
    candidates = []
    for chunk in chunks:
        chunk_text_lower = chunk.text.lower()
        
        # Check if any keyword appears in chunk
        for keyword in keywords:
            if keyword.lower() in chunk_text_lower:
                candidates.append(chunk)
                break  # One match is enough
    
    logger.debug(
        f"Keyword filter for {clause_type}: {len(candidates)}/{len(chunks)} chunks matched"
    )
    
    return candidates


# ── Clause Extraction ─────────────────────────────────────────────────────────


async def extract_clauses_from_document(
    db: AsyncSession,
    document_id: uuid.UUID,
    clause_type: str,
) -> list[ClauseCandidate]:
    """
    Extract all clauses of a specific type from a document.
    
    Two-phase approach per architecture.md §6.5:
    1. Keyword pre-filter to narrow candidate chunks
    2. LLM classification on candidates using claude-haiku
    
    Args:
        db: Database session
        document_id: UUID of document to extract from
        clause_type: Type of clause to extract (one of 10 predefined types)
    
    Returns:
        List of ClauseCandidate objects with risk assessments
    
    Raises:
        ValueError: Invalid clause_type or LLM error
    """
    # Validate clause type
    if clause_type not in CLAUSE_TYPE_KEYWORDS:
        raise ValueError(
            f"Invalid clause_type: {clause_type}. "
            f"Must be one of {list(CLAUSE_TYPE_KEYWORDS.keys())}"
        )
    
    logger.info(
        f"Extracting {clause_type} clauses from document {document_id}"
    )
    
    # Fetch all chunks for the document
    stmt = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    )
    result = await db.execute(stmt)
    all_chunks = result.scalars().all()
    
    if not all_chunks:
        logger.warning(f"No chunks found for document {document_id}")
        return []
    
    logger.debug(f"Document has {len(all_chunks)} total chunks")
    
    # Phase 1: Keyword pre-filter
    candidate_chunks = filter_chunks_by_keywords(all_chunks, clause_type)
    
    if not candidate_chunks:
        logger.info(
            f"No keyword matches for {clause_type} in document {document_id}"
        )
        return []
    
    logger.info(
        f"Keyword filter found {len(candidate_chunks)} candidate chunks "
        f"for {clause_type}"
    )
    
    # Phase 2: LLM classification on candidates
    try:
        response = await generate_grounded_response(
            task="extract_clauses",
            context_chunks=candidate_chunks,
            user_input=clause_type,  # Tell LLM which clause type to extract
            reading_level=None,
        )
        
        # Parse JSON response
        # Response is either a JSON array directly or wrapped in the content field
        try:
            if response.content.startswith('['):
                clauses_data = json.loads(response.content)
            else:
                # Try to extract JSON from response
                import re
                json_match = re.search(r'\[.*\]', response.content, re.DOTALL)
                if json_match:
                    clauses_data = json.loads(json_match.group(0))
                else:
                    raise ValueError(
                        f"Could not parse clause extraction response as JSON array. "
                        f"Response: {response.content[:200]}"
                    )
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Failed to parse clause extraction response: {e}. "
                f"Response was: {response.content[:200]}"
            ) from e
        
        # Validate and convert to ClauseCandidate objects
        clauses: list[ClauseCandidate] = []
        for clause_dict in clauses_data:
            try:
                clause = ClauseCandidate(**clause_dict)
                
                # Additional validation: ensure chunk_id is in our candidate set
                if not any(c.id == clause.chunk_id for c in candidate_chunks):
                    logger.warning(
                        f"LLM returned clause with chunk_id {clause.chunk_id} "
                        f"not in candidate set - skipping"
                    )
                    continue
                
                clauses.append(clause)
                
            except Exception as e:
                logger.error(
                    f"Failed to validate clause from LLM response: {e}. "
                    f"Clause data: {clause_dict}"
                )
                # Continue with other clauses
                continue
        
        logger.info(
            f"Extracted {len(clauses)} {clause_type} clauses from document {document_id}"
        )
        
        return clauses
        
    except Exception as e:
        logger.error(
            f"Clause extraction failed for document {document_id}, "
            f"type {clause_type}: {e}"
        )
        raise ValueError(f"Clause extraction failed: {e}") from e
