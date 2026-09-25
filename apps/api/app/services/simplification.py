"""
Simplification Service — LegalLens
Implements: architecture.md §3 step 5 map-reduce simplification.
Responsibility: Full-document and per-clause simplification with reading levels.
"""

from __future__ import annotations

import logging
import uuid
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_chunk import DocumentChunk
from app.services.llm_orchestration import Citation, generate_grounded_response

logger = logging.getLogger(__name__)


# ── Data Models ───────────────────────────────────────────────────────────────


class ChunkSimplification(BaseModel):
    """Result of simplifying a single chunk."""
    chunk_id: uuid.UUID
    simplified_text: str
    citations: list[Citation]


class SimplificationResult(BaseModel):
    """Result of full document simplification."""
    document_id: uuid.UUID
    simplified_text: str
    reading_level: Literal["elementary", "plain_english", "detailed"]
    citations: list[Citation]
    chunk_count: int


# ── Configuration ─────────────────────────────────────────────────────────────


# Threshold for map-reduce vs single-pass
# Per architecture.md §3 step 5: documents ≤5 chunks use single-pass, >5 use map-reduce
MAP_REDUCE_THRESHOLD = 5


# ── Single Chunk Simplification ───────────────────────────────────────────────


async def simplify_single_chunk(
    chunk: DocumentChunk,
    reading_level: Literal["elementary", "plain_english", "detailed"],
) -> ChunkSimplification:
    """
    Simplify a single chunk using LLM orchestration.
    
    Part of the map phase in map-reduce simplification.
    
    Args:
        chunk: DocumentChunk to simplify
        reading_level: Target reading level
    
    Returns:
        ChunkSimplification with simplified text and citations
    """
    logger.debug(
        f"Simplifying chunk {chunk.id} (index={chunk.chunk_index}, "
        f"tokens={chunk.token_count}) to {reading_level}"
    )
    
    response = await generate_grounded_response(
        task="simplify",
        context_chunks=[chunk],
        user_input="",
        reading_level=reading_level,
    )
    
    return ChunkSimplification(
        chunk_id=chunk.id,
        simplified_text=response.content,
        citations=response.citations,
    )


# ── Full Document Simplification ──────────────────────────────────────────────


async def simplify_document(
    db: AsyncSession,
    document_id: uuid.UUID,
    reading_level: Literal["elementary", "plain_english", "detailed"] = "plain_english",
) -> SimplificationResult:
    """
    Simplify an entire document with map-reduce pattern for large documents.
    
    Per architecture.md §3 step 5:
    - Small documents (≤5 chunks): single-pass simplification
    - Large documents (>5 chunks): map-reduce (per-chunk + coherence pass)
    
    Args:
        db: Database session
        document_id: UUID of document to simplify
        reading_level: Target reading level (elementary/plain_english/detailed)
    
    Returns:
        SimplificationResult with simplified text and aggregated citations
    
    Raises:
        ValueError: Invalid reading_level or no chunks found
    """
    # Validation
    valid_levels = {"elementary", "plain_english", "detailed"}
    if reading_level not in valid_levels:
        raise ValueError(
            f"reading_level must be one of {valid_levels}, got: {reading_level}"
        )
    
    # Fetch all chunks for the document
    stmt = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    )
    result = await db.execute(stmt)
    chunks = result.scalars().all()
    
    if not chunks:
        raise ValueError(f"No chunks found for document {document_id}")
    
    # Sort by chunk_index to ensure correct order (defensive, query already orders)
    chunks = sorted(chunks, key=lambda c: c.chunk_index)
    
    chunk_count = len(chunks)
    logger.info(
        f"Simplifying document {document_id}: {chunk_count} chunks, "
        f"reading_level={reading_level}"
    )
    
    # Choose strategy based on chunk count
    if chunk_count <= MAP_REDUCE_THRESHOLD:
        # Small document: single-pass simplification
        simplified_text, citations = await _simplify_single_pass(
            chunks=chunks,
            reading_level=reading_level,
        )
    else:
        # Large document: map-reduce
        simplified_text, citations = await _simplify_map_reduce(
            chunks=chunks,
            reading_level=reading_level,
        )
    
    logger.info(
        f"Document {document_id} simplified: {len(simplified_text)} chars, "
        f"{len(citations)} citations"
    )
    
    return SimplificationResult(
        document_id=document_id,
        simplified_text=simplified_text,
        reading_level=reading_level,
        citations=citations,
        chunk_count=chunk_count,
    )


async def _simplify_single_pass(
    chunks: list[DocumentChunk],
    reading_level: str,
) -> tuple[str, list[Citation]]:
    """
    Single-pass simplification for small documents.
    
    Sends all chunks to LLM in one call.
    """
    logger.debug(f"Using single-pass simplification for {len(chunks)} chunks")
    
    response = await generate_grounded_response(
        task="simplify",
        context_chunks=chunks,
        user_input="",
        reading_level=reading_level,
    )
    
    return response.content, response.citations


async def _simplify_map_reduce(
    chunks: list[DocumentChunk],
    reading_level: str,
) -> tuple[str, list[Citation]]:
    """
    Map-reduce simplification for large documents.
    
    Per architecture.md §3 step 5:
    1. Map phase: Simplify each chunk independently
    2. Reduce phase: Coherence pass to combine simplified chunks
    
    Args:
        chunks: Ordered list of document chunks
        reading_level: Target reading level
    
    Returns:
        Tuple of (simplified_text, aggregated_citations)
    """
    logger.info(
        f"Using map-reduce simplification for {len(chunks)} chunks "
        f"(threshold={MAP_REDUCE_THRESHOLD})"
    )
    
    # ── Map Phase ─────────────────────────────────────────────────────────────
    # Simplify each chunk independently
    
    chunk_simplifications: list[ChunkSimplification] = []
    
    for chunk in chunks:
        try:
            simplified_chunk = await simplify_single_chunk(
                chunk=chunk,
                reading_level=reading_level,
            )
            chunk_simplifications.append(simplified_chunk)
            
        except Exception as e:
            logger.error(
                f"Failed to simplify chunk {chunk.id} (index={chunk.chunk_index}): {e}"
            )
            # Continue with other chunks - partial simplification better than none
            # Include placeholder for failed chunk
            chunk_simplifications.append(
                ChunkSimplification(
                    chunk_id=chunk.id,
                    simplified_text=f"[Error simplifying chunk {chunk.chunk_index}]",
                    citations=[],
                )
            )
    
    logger.debug(f"Map phase complete: {len(chunk_simplifications)} chunks simplified")
    
    # ── Reduce Phase ──────────────────────────────────────────────────────────
    # Coherence pass: combine simplified chunks into a cohesive document
    
    # Build a synthetic "document" from the simplified chunks for the coherence pass
    # We create pseudo-chunks from the map results to feed to the LLM
    coherence_chunks = []
    for i, simplified in enumerate(chunk_simplifications):
        # Find original chunk for metadata
        original_chunk = next(c for c in chunks if c.id == simplified.chunk_id)
        
        # Create a pseudo-chunk with simplified text
        pseudo_chunk = DocumentChunk(
            id=simplified.chunk_id,
            document_id=original_chunk.document_id,
            chunk_index=i,
            page_number=original_chunk.page_number,
            text=simplified.simplified_text,
            token_count=len(simplified.simplified_text.split()),  # Rough estimate
            embedding=None,
        )
        coherence_chunks.append(pseudo_chunk)
    
    logger.debug("Running coherence pass (reduce phase)")
    
    # Coherence pass: ask LLM to combine into cohesive narrative
    coherence_response = await generate_grounded_response(
        task="simplify",
        context_chunks=coherence_chunks,
        user_input=(
            "Combine the following simplified sections into a single, "
            "cohesive document. Ensure smooth transitions between sections. "
            "Maintain all key information. Remove any redundancy."
        ),
        reading_level=reading_level,
    )
    
    # Aggregate citations from both map and reduce phases
    all_citations: list[Citation] = []
    citation_ids_seen = set()
    
    # Add citations from map phase
    for simplified in chunk_simplifications:
        for citation in simplified.citations:
            citation_key = (citation.chunk_id, citation.page_number)
            if citation_key not in citation_ids_seen:
                all_citations.append(citation)
                citation_ids_seen.add(citation_key)
    
    # Add citations from coherence pass
    for citation in coherence_response.citations:
        citation_key = (citation.chunk_id, citation.page_number)
        if citation_key not in citation_ids_seen:
            all_citations.append(citation)
            citation_ids_seen.add(citation_key)
    
    logger.debug(
        f"Map-reduce complete: {len(all_citations)} unique citations aggregated"
    )
    
    return coherence_response.content, all_citations
