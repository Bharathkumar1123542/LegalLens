"""
Unit tests — simplification service
Tests: Map-reduce simplification, reading levels, citation aggregation, coherence pass.
Covers: architecture.md §3 step 5 "per-chunk simplify, then coherence pass".
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.document_chunk import DocumentChunk
from app.services.simplification import (
    SimplificationResult,
    simplify_document,
    simplify_single_chunk,
)


class TestSimplifySingleChunk:
    """Test single chunk simplification."""

    @patch("app.services.simplification.generate_grounded_response")
    async def test_simplify_single_chunk_elementary(self, mock_generate):
        """Test elementary reading level simplification."""
        chunk = DocumentChunk(
            id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_index=0,
            page_number=1,
            text="The Lessee hereby covenants to pay rent.",
            token_count=50,
            embedding=None,
        )
        
        # Mock LLM response
        from app.services.llm_orchestration import Citation, GroundedResponse
        mock_response = GroundedResponse(
            task="simplify",
            content="The renter must pay rent.",
            citations=[
                Citation(
                    chunk_id=chunk.id,
                    page_number=1,
                    excerpt="Lessee hereby covenants",
                )
            ],
            model_used="claude-sonnet-4-20250514",
        )
        mock_generate.return_value = mock_response
        
        result = await simplify_single_chunk(
            chunk=chunk,
            reading_level="elementary",
        )
        
        assert result.simplified_text == "The renter must pay rent."
        assert len(result.citations) == 1
        mock_generate.assert_awaited_once_with(
            task="simplify",
            context_chunks=[chunk],
            user_input="",
            reading_level="elementary",
        )

    @patch("app.services.simplification.generate_grounded_response")
    async def test_simplify_single_chunk_plain_english(self, mock_generate):
        """Test plain_english reading level (default)."""
        chunk = DocumentChunk(
            id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_index=0,
            page_number=1,
            text="The parties agree to arbitration.",
            token_count=50,
            embedding=None,
        )
        
        from app.services.llm_orchestration import GroundedResponse
        mock_generate.return_value = GroundedResponse(
            task="simplify",
            content="The parties agree to settle disputes through arbitration.",
            citations=[],
            model_used="claude-sonnet-4-20250514",
        )
        
        result = await simplify_single_chunk(
            chunk=chunk,
            reading_level="plain_english",
        )
        
        assert "arbitration" in result.simplified_text
        mock_generate.assert_awaited_once()


@pytest.mark.asyncio
class TestSimplifyDocument:
    """Test full document map-reduce simplification."""

    @patch("app.services.simplification.generate_grounded_response")
    async def test_simplify_small_document_single_pass(self, mock_generate):
        """Small document (≤5 chunks) uses single-pass simplification."""
        db = AsyncMock()
        document_id = uuid.uuid4()
        
        # Mock 3 chunks
        chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                chunk_index=i,
                page_number=i+1,
                text=f"Legal text chunk {i}.",
                token_count=100,
                embedding=[0.1] * 1024,
            )
            for i in range(3)
        ]
        # Mock DB query: db.execute() is async and returns a sync result object
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = chunks
        async def mock_execute(*args, **kwargs):
            return mock_result
        db.execute = mock_execute
        
        # Mock single LLM response for all chunks
        from app.services.llm_orchestration import Citation, GroundedResponse
        mock_response = GroundedResponse(
            task="simplify",
            content="Simplified version of all three chunks.",
            citations=[
                Citation(chunk_id=chunks[0].id, page_number=1, excerpt="chunk 0"),
                Citation(chunk_id=chunks[1].id, page_number=2, excerpt="chunk 1"),
            ],
            model_used="claude-sonnet-4-20250514",
        )
        mock_generate.return_value = mock_response
        
        result = await simplify_document(
            db=db,
            document_id=document_id,
            reading_level="plain_english",
        )
        
        assert result.simplified_text == "Simplified version of all three chunks."
        assert len(result.citations) == 2
        assert result.reading_level == "plain_english"
        
        # Should call LLM once with all chunks
        mock_generate.assert_awaited_once()
        call_args = mock_generate.call_args.kwargs
        assert len(call_args["context_chunks"]) == 3

    @patch("app.services.simplification.simplify_single_chunk")
    @patch("app.services.simplification.generate_grounded_response")
    async def test_simplify_large_document_map_reduce(self, mock_generate, mock_single):
        """Large document (>5 chunks) uses map-reduce pattern."""
        db = AsyncMock()
        document_id = uuid.uuid4()
        
        # Mock 10 chunks (triggers map-reduce)
        chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                chunk_index=i,
                page_number=(i // 2) + 1,
                text=f"Legal text chunk {i} with terms and conditions.",
                token_count=200,
                embedding=[0.1] * 1024,
            )
            for i in range(10)
        ]
        # Mock DB query: db.execute() is async and returns a sync result object
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = chunks
        # Make db.execute() async but return the sync mock_result when awaited
        async def mock_execute(*args, **kwargs):
            return mock_result
        db.execute = mock_execute
        
        # Mock per-chunk simplifications (map phase)
        from app.services.llm_orchestration import Citation
        mock_single_results = []
        for i, chunk in enumerate(chunks):
            from app.services.simplification import ChunkSimplification
            mock_single_results.append(
                ChunkSimplification(
                    chunk_id=chunk.id,
                    simplified_text=f"Simple chunk {i}.",
                    citations=[
                        Citation(
                            chunk_id=chunk.id,
                            page_number=chunk.page_number,
                            excerpt=f"excerpt {i}",
                        )
                    ],
                )
            )
        mock_single.side_effect = mock_single_results
        
        # Mock coherence pass (reduce phase)
        from app.services.llm_orchestration import GroundedResponse
        mock_coherence = GroundedResponse(
            task="simplify",
            content="Coherent simplified version combining all chunks.",
            citations=[
                Citation(chunk_id=chunks[0].id, page_number=1, excerpt="chunk 0"),
                Citation(chunk_id=chunks[5].id, page_number=3, excerpt="chunk 5"),
            ],
            model_used="claude-sonnet-4-20250514",
        )
        mock_generate.return_value = mock_coherence
        
        result = await simplify_document(
            db=db,
            document_id=document_id,
            reading_level="detailed",
        )
        
        # Should have called per-chunk simplify 10 times (map)
        assert mock_single.call_count == 10
        
        # Should have called coherence pass once (reduce)
        mock_generate.assert_awaited_once()
        
        assert "Coherent simplified version" in result.simplified_text
        assert len(result.citations) == 2

    async def test_simplify_document_no_chunks(self):
        """Handle document with no chunks."""
        db = AsyncMock()
        document_id = uuid.uuid4()
        
        # Mock DB query: db.execute() is async and returns a sync result object
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        
        async def mock_execute(*args, **kwargs):
            return mock_result
        
        db.execute = mock_execute
        
        with pytest.raises(ValueError, match="No chunks found"):
            await simplify_document(
                db=db,
                document_id=document_id,
                reading_level="plain_english",
            )

    @patch("app.services.simplification.generate_grounded_response")
    async def test_simplify_document_validates_reading_level(self, mock_generate):
        """Validate reading_level parameter."""
        db = AsyncMock()
        document_id = uuid.uuid4()
        
        chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                chunk_index=0,
                page_number=1,
                text="Text",
                token_count=50,
                embedding=None,
            )
        ]
        
        # Mock DB query: db.execute() is async and returns a sync result object
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = chunks
        
        async def mock_execute(*args, **kwargs):
            return mock_result
        
        db.execute = mock_execute
        
        with pytest.raises(ValueError, match="reading_level must be one of"):
            await simplify_document(
                db=db,
                document_id=document_id,
                reading_level="invalid_level",
            )

    @patch("app.services.simplification.simplify_single_chunk")
    @patch("app.services.simplification.generate_grounded_response")
    async def test_simplify_aggregates_citations(self, mock_generate, mock_single):
        """Verify citations from all chunks are aggregated."""
        db = AsyncMock()
        document_id = uuid.uuid4()
        
        chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                chunk_index=i,
                page_number=i+1,
                text=f"Chunk {i}",
                token_count=100,
                embedding=None,
            )
            for i in range(8)
        ]
        
        # Mock DB query: db.execute() is async and returns a sync result object
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = chunks
        
        async def mock_execute(*args, **kwargs):
            return mock_result
        
        db.execute = mock_execute
        
        # Mock per-chunk results with citations
        from app.services.llm_orchestration import Citation
        from app.services.simplification import ChunkSimplification
        mock_single_results = []
        for i, chunk in enumerate(chunks):
            mock_single_results.append(
                ChunkSimplification(
                    chunk_id=chunk.id,
                    simplified_text=f"Simple {i}",
                    citations=[
                        Citation(
                            chunk_id=chunk.id,
                            page_number=i+1,
                            excerpt=f"excerpt {i}",
                        )
                    ],
                )
            )
        mock_single.side_effect = mock_single_results
        
        # Mock coherence pass
        from app.services.llm_orchestration import GroundedResponse
        mock_generate.return_value = GroundedResponse(
            task="simplify",
            content="Final text",
            citations=[
                Citation(chunk_id=chunks[3].id, page_number=4, excerpt="chunk 3"),
            ],
            model_used="claude-sonnet-4-20250514",
        )
        
        result = await simplify_document(
            db=db,
            document_id=document_id,
            reading_level="plain_english",
        )
        
        # Citations should include those from coherence pass
        assert len(result.citations) >= 1
        assert any(c.page_number == 4 for c in result.citations)

    @patch("app.services.simplification.generate_grounded_response")
    async def test_simplify_preserves_chunk_order(self, mock_generate):
        """Verify chunks processed in order by chunk_index."""
        db = AsyncMock()
        document_id = uuid.uuid4()
        
        # Create chunks out of order
        chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                chunk_index=2,
                page_number=2,
                text="Third chunk",
                token_count=100,
                embedding=None,
            ),
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                chunk_index=0,
                page_number=1,
                text="First chunk",
                token_count=100,
                embedding=None,
            ),
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                chunk_index=1,
                page_number=1,
                text="Second chunk",
                token_count=100,
                embedding=None,
            ),
        ]
        
        # Mock DB query: db.execute() is async and returns a sync result object
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = chunks
        
        async def mock_execute(*args, **kwargs):
            return mock_result
        
        db.execute = mock_execute
        
        from app.services.llm_orchestration import GroundedResponse
        mock_generate.return_value = GroundedResponse(
            task="simplify",
            content="Simplified",
            citations=[],
            model_used="claude-sonnet-4-20250514",
        )
        
        await simplify_document(
            db=db,
            document_id=document_id,
            reading_level="plain_english",
        )
        
        # Verify chunks were sorted before processing
        call_args = mock_generate.call_args.kwargs
        ordered_chunks = call_args["context_chunks"]
        assert ordered_chunks[0].text == "First chunk"
        assert ordered_chunks[1].text == "Second chunk"
        assert ordered_chunks[2].text == "Third chunk"

    @patch("app.services.simplification.generate_grounded_response")
    async def test_simplify_handles_llm_error(self, mock_generate):
        """Handle LLM generation errors gracefully."""
        db = AsyncMock()
        document_id = uuid.uuid4()
        
        chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                chunk_index=0,
                page_number=1,
                text="Text",
                token_count=50,
                embedding=None,
            )
        ]
        
        # Mock DB query: db.execute() is async and returns a sync result object
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = chunks
        
        async def mock_execute(*args, **kwargs):
            return mock_result
        
        db.execute = mock_execute
        
        mock_generate.side_effect = ValueError("LLM generation failed")
        
        with pytest.raises(ValueError, match="LLM generation failed"):
            await simplify_document(
                db=db,
                document_id=document_id,
                reading_level="plain_english",
            )


class TestSimplificationResult:
    """Test SimplificationResult data structure."""

    def test_simplification_result_creation(self):
        """Create valid SimplificationResult."""
        from app.services.llm_orchestration import Citation
        
        citation = Citation(
            chunk_id=uuid.uuid4(),
            page_number=3,
            excerpt="Original text",
        )
        
        from app.services.simplification import SimplificationResult
        result = SimplificationResult(
            document_id=uuid.uuid4(),
            simplified_text="Simplified document text.",
            reading_level="plain_english",
            citations=[citation],
            chunk_count=10,
        )
        
        assert result.reading_level == "plain_english"
        assert result.chunk_count == 10
        assert len(result.citations) == 1


class TestMapReduceThreshold:
    """Test map-reduce threshold logic."""

    @patch("app.services.simplification.generate_grounded_response")
    async def test_threshold_at_boundary(self, mock_generate):
        """Test behavior at exactly 5 chunks (boundary)."""
        db = AsyncMock()
        document_id = uuid.uuid4()
        
        # Exactly 5 chunks - should use single-pass
        chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                chunk_index=i,
                page_number=i+1,
                text=f"Chunk {i}",
                token_count=100,
                embedding=None,
            )
            for i in range(5)
        ]
        
        # Mock DB query: db.execute() is async and returns a sync result object
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = chunks
        
        async def mock_execute(*args, **kwargs):
            return mock_result
        
        db.execute = mock_execute
        
        from app.services.llm_orchestration import GroundedResponse
        mock_generate.return_value = GroundedResponse(
            task="simplify",
            content="Simplified",
            citations=[],
            model_used="claude-sonnet-4-20250514",
        )
        
        await simplify_document(
            db=db,
            document_id=document_id,
            reading_level="plain_english",
        )
        
        # Should call once for single-pass (not map-reduce)
        assert mock_generate.call_count == 1
        call_args = mock_generate.call_args.kwargs
        assert len(call_args["context_chunks"]) == 5

