"""
Embedding Service — LegalLens Phase 2
Implements: architecture.md §6.3 Embedding & Retrieval Module.
Uses Voyage AI voyage-3 model (1024 dimensions) for document embeddings.
architecture.md §10: batch to largest supported request size (100 texts per call).
"""

from __future__ import annotations

import uuid

import structlog
import voyageai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pgvector.sqlalchemy import Vector

from app.core.config import settings
from app.models.document_chunk import DocumentChunk

log = structlog.get_logger(__name__)

# architecture.md §4: Voyage AI voyage-3 produces 1024-dim vectors
EXPECTED_VECTOR_DIM = 1024
BATCH_SIZE = 100  # Voyage AI max batch size


def embed_single_text(text: str) -> list[float]:
    """
    Embed a single text string using Voyage AI.
    Returns a 1024-dimensional vector.
    
    Raises:
        ValueError: If embedding fails or dimension mismatch
    """
    try:
        client = voyageai.Client(api_key=settings.VOYAGE_API_KEY)
        response = client.embed(
            [text],
            model="voyage-3",
            input_type="document",
        )
        
        vector = response.embeddings[0]
        
        if len(vector) != EXPECTED_VECTOR_DIM:
            raise ValueError(
                f"Expected {EXPECTED_VECTOR_DIM} dimensions, got {len(vector)}"
            )
        
        log.info("embedding.single_text", char_count=len(text))
        return vector
        
    except Exception as exc:
        log.error("embedding.single_failed", error=str(exc))
        raise ValueError(f"Embedding failed: {exc}") from exc


async def embed_chunks(db: AsyncSession, document_id: uuid.UUID) -> None:
    """
    Embed all chunks for a document using Voyage AI.
    Processes in batches of BATCH_SIZE (architecture.md §10).
    Updates chunk.embedding in place and commits.
    
    Args:
        db: Database session
        document_id: Document to embed chunks for
    """
    # Fetch all chunks without embeddings
    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .where(DocumentChunk.embedding.is_(None))
        .order_by(DocumentChunk.chunk_index)
    )
    chunks = result.scalars().all()
    
    if not chunks:
        log.warning("embedding.no_chunks", document_id=str(document_id))
        return
    
    try:
        client = voyageai.Client(api_key=settings.VOYAGE_API_KEY)
        
        # Process in batches
        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i:i + BATCH_SIZE]
            texts = [chunk.text for chunk in batch]
            
            response = client.embed(
                texts,
                model="voyage-3",
                input_type="document",
            )
            
            # Write embeddings back to chunks
            for chunk, embedding in zip(batch, response.embeddings):
                if len(embedding) != EXPECTED_VECTOR_DIM:
                    raise ValueError(
                        f"Chunk {chunk.id}: expected {EXPECTED_VECTOR_DIM} dims, got {len(embedding)}"
                    )
                chunk.embedding = embedding
            
            log.info(
                "embedding.batch_completed",
                document_id=str(document_id),
                batch_start=i,
                batch_size=len(batch),
            )
        
        await db.commit()
        log.info(
            "embedding.document_completed",
            document_id=str(document_id),
            total_chunks=len(chunks),
        )
        
    except Exception as exc:
        await db.rollback()
        log.error(
            "embedding.document_failed",
            document_id=str(document_id),
            error=str(exc),
        )
        raise ValueError(f"Failed to embed document chunks: {exc}") from exc


async def retrieve_relevant_chunks(
    db: AsyncSession,
    document_id: uuid.UUID,
    query: str,
    top_k: int = 8,
) -> list[DocumentChunk]:
    """
    Retrieve top-k most relevant chunks for a query using cosine similarity.
    Implements: architecture.md §6.3 retrieve_relevant_chunks, §3 step 4.
    
    Args:
        db: Database session
        document_id: Document to search within
        query: User query text
        top_k: Number of chunks to return (default 8 per architecture.md §6.4)
    
    Returns:
        List of DocumentChunk objects, ordered by similarity (descending)
    
    Raises:
        ValueError: If top_k is invalid
    """
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    
    # Embed the query
    query_vector = embed_single_text(query)
    
    # pgvector cosine similarity: <-> operator
    # Returns chunks ordered by similarity (most similar first)
    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .where(DocumentChunk.embedding.isnot(None))
        .order_by(DocumentChunk.embedding.cosine_distance(query_vector))
        .limit(top_k)
    )
    chunks = result.scalars().all()
    
    log.info(
        "retrieval.completed",
        document_id=str(document_id),
        query_len=len(query),
        retrieved_count=len(chunks),
    )
    return list(chunks)
