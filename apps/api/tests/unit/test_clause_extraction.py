"""
Unit tests — clause extraction service
Tests: Keyword pre-filtering, LLM classification, 10 clause types, 3 risk levels.
Covers: architecture.md §6.5 Clause & Risk Extraction Service.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.document_chunk import DocumentChunk
from app.services.clause_extraction import (
    ClauseCandidate,
    extract_clauses_from_document,
    filter_chunks_by_keywords,
    CLAUSE_TYPE_KEYWORDS,
)


class TestKeywordFiltering:
    """Test keyword-based pre-filtering before LLM classification."""

    def test_filter_chunks_by_keywords_indemnification(self):
        """Test keyword filtering for indemnification clauses."""
        chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                chunk_index=0,
                page_number=1,
                text="The Client agrees to indemnify and hold harmless the Provider.",
                token_count=50,
                embedding=None,
            ),
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                chunk_index=1,
                page_number=1,
                text="This agreement shall be governed by California law.",
                token_count=50,
                embedding=None,
            ),
        ]
        
        candidates = filter_chunks_by_keywords(chunks, "indemnification")
        
        # Only first chunk should match (contains "indemnify")
        assert len(candidates) == 1
        assert "indemnify" in candidates[0].text.lower()

    def test_filter_chunks_by_keywords_termination(self):
        """Test keyword filtering for termination clauses."""
        chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                chunk_index=0,
                page_number=1,
                text="Either party may terminate this agreement with 30 days notice.",
                token_count=50,
                embedding=None,
            ),
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                chunk_index=1,
                page_number=2,
                text="Payment is due within 15 days of invoice.",
                token_count=50,
                embedding=None,
            ),
        ]
        
        candidates = filter_chunks_by_keywords(chunks, "termination")
        
        assert len(candidates) == 1
        assert "terminate" in candidates[0].text.lower()

    def test_filter_chunks_returns_empty_for_no_matches(self):
        """Return empty list when no keywords match."""
        chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                chunk_index=0,
                page_number=1,
                text="This is generic contract text with no specific clauses.",
                token_count=50,
                embedding=None,
            ),
        ]
        
        candidates = filter_chunks_by_keywords(chunks, "indemnification")
        
        assert candidates == []

    def test_filter_chunks_case_insensitive(self):
        """Keyword matching should be case-insensitive."""
        chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                chunk_index=0,
                page_number=1,
                text="The INDEMNIFICATION clause applies to all parties.",
                token_count=50,
                embedding=None,
            ),
        ]
        
        candidates = filter_chunks_by_keywords(chunks, "indemnification")
        
        assert len(candidates) == 1

    def test_keyword_coverage_all_clause_types(self):
        """Verify keywords exist for all 10 clause types."""
        expected_types = {
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
        }
        
        assert set(CLAUSE_TYPE_KEYWORDS.keys()) == expected_types
        
        # Each type should have at least one keyword
        for clause_type, keywords in CLAUSE_TYPE_KEYWORDS.items():
            assert len(keywords) > 0, f"{clause_type} has no keywords"


@pytest.mark.asyncio
class TestClauseExtraction:
    """Test full clause extraction flow."""

    @patch("app.services.clause_extraction.generate_grounded_response")
    async def test_extract_clauses_single_type(self, mock_generate):
        """Extract clauses of a single type from document."""
        db = AsyncMock()
        document_id = uuid.uuid4()
        
        # Mock chunks with indemnification keywords
        chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                chunk_index=0,
                page_number=1,
                text="Client shall indemnify Provider for all claims.",
                token_count=50,
                embedding=None,
            ),
        ]
        
        # Mock DB query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = chunks
        async def mock_execute(*args, **kwargs):
            return mock_result
        db.execute = mock_execute
        
        # Mock LLM response with extracted clause
        from app.services.llm_orchestration import GroundedResponse
        mock_response = GroundedResponse(
            task="extract_clauses",
            content='[{"clause_type": "indemnification", "text_excerpt": "Client shall indemnify Provider", "start_offset": 0, "end_offset": 32, "chunk_id": "' + str(chunks[0].id) + '", "risk_level": "high", "risk_rationale": "One-sided indemnification with no carve-outs."}]',
            citations=[],
            model_used="claude-haiku-4-5-20251001",
        )
        mock_generate.return_value = mock_response
        
        clauses = await extract_clauses_from_document(
            db=db,
            document_id=document_id,
            clause_type="indemnification",
        )
        
        assert len(clauses) == 1
        assert clauses[0].clause_type == "indemnification"
        assert clauses[0].risk_level == "high"
        assert clauses[0].chunk_id == chunks[0].id

    @patch("app.services.clause_extraction.generate_grounded_response")
    async def test_extract_clauses_multiple_matches(self, mock_generate):
        """Extract multiple clauses of same type from different chunks."""
        db = AsyncMock()
        document_id = uuid.uuid4()
        
        # Multiple chunks with termination keywords
        chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                chunk_index=0,
                page_number=1,
                text="Either party may terminate with 30 days notice.",
                token_count=50,
                embedding=None,
            ),
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                chunk_index=5,
                page_number=3,
                text="Provider may terminate immediately for non-payment.",
                token_count=50,
                embedding=None,
            ),
        ]
        
        # Mock DB query
        all_chunks = chunks + [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                chunk_index=2,
                page_number=2,
                text="Unrelated content about payments.",
                token_count=50,
                embedding=None,
            ),
        ]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = all_chunks
        async def mock_execute(*args, **kwargs):
            return mock_result
        db.execute = mock_execute
        
        # Mock LLM response with two clauses
        from app.services.llm_orchestration import GroundedResponse
        mock_response = GroundedResponse(
            task="extract_clauses",
            content='[{"clause_type": "termination", "text_excerpt": "Either party may terminate", "start_offset": 0, "end_offset": 26, "chunk_id": "' + str(chunks[0].id) + '", "risk_level": "low", "risk_rationale": "Mutual termination rights."}, {"clause_type": "termination", "text_excerpt": "Provider may terminate immediately", "start_offset": 0, "end_offset": 34, "chunk_id": "' + str(chunks[1].id) + '", "risk_level": "medium", "risk_rationale": "Asymmetric termination rights."}]',
            citations=[],
            model_used="claude-haiku-4-5-20251001",
        )
        mock_generate.return_value = mock_response
        
        clauses = await extract_clauses_from_document(
            db=db,
            document_id=document_id,
            clause_type="termination",
        )
        
        assert len(clauses) == 2
        assert all(c.clause_type == "termination" for c in clauses)
        assert clauses[0].risk_level == "low"
        assert clauses[1].risk_level == "medium"

    @patch("app.services.clause_extraction.generate_grounded_response")
    async def test_extract_clauses_no_matches(self, mock_generate):
        """Handle case where keyword filter finds candidates but LLM finds no clauses."""
        db = AsyncMock()
        document_id = uuid.uuid4()
        
        chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                chunk_index=0,
                page_number=1,
                text="The indemnity provision was discussed but not included.",
                token_count=50,
                embedding=None,
            ),
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = chunks
        async def mock_execute(*args, **kwargs):
            return mock_result
        db.execute = mock_execute
        
        # LLM returns empty array
        from app.services.llm_orchestration import GroundedResponse
        mock_response = GroundedResponse(
            task="extract_clauses",
            content="[]",
            citations=[],
            model_used="claude-haiku-4-5-20251001",
        )
        mock_generate.return_value = mock_response
        
        clauses = await extract_clauses_from_document(
            db=db,
            document_id=document_id,
            clause_type="indemnification",
        )
        
        assert clauses == []

    async def test_extract_clauses_no_keyword_matches(self):
        """Handle case where keyword filter finds no candidates."""
        db = AsyncMock()
        document_id = uuid.uuid4()
        
        # Chunks with no indemnification keywords
        chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                chunk_index=0,
                page_number=1,
                text="This agreement is governed by California law.",
                token_count=50,
                embedding=None,
            ),
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = chunks
        async def mock_execute(*args, **kwargs):
            return mock_result
        db.execute = mock_execute
        
        clauses = await extract_clauses_from_document(
            db=db,
            document_id=document_id,
            clause_type="indemnification",
        )
        
        # Should return empty without calling LLM
        assert clauses == []

    @patch("app.services.clause_extraction.generate_grounded_response")
    async def test_extract_clauses_validates_offsets(self, mock_generate):
        """Invalid offsets are logged and skipped, not raised."""
        db = AsyncMock()
        document_id = uuid.uuid4()
        
        chunk_id = uuid.uuid4()
        chunks = [
            DocumentChunk(
                id=chunk_id,
                document_id=document_id,
                chunk_index=0,
                page_number=1,
                text="Client shall indemnify Provider.",
                token_count=50,
                embedding=None,
            ),
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = chunks
        async def mock_execute(*args, **kwargs):
            return mock_result
        db.execute = mock_execute
        
        # Mock response with invalid offsets (end < start) - should be skipped
        from app.services.llm_orchestration import GroundedResponse
        mock_response = GroundedResponse(
            task="extract_clauses",
            content='[{"clause_type": "indemnification", "text_excerpt": "indemnify", "start_offset": 20, "end_offset": 10, "chunk_id": "' + str(chunk_id) + '", "risk_level": "high", "risk_rationale": "Test."}]',
            citations=[],
            model_used="claude-haiku-4-5-20251001",
        )
        mock_generate.return_value = mock_response
        
        # Should return empty list (invalid clause skipped), not raise
        clauses = await extract_clauses_from_document(
            db=db,
            document_id=document_id,
            clause_type="indemnification",
        )
        
        assert clauses == []

    @patch("app.services.clause_extraction.generate_grounded_response")
    async def test_extract_clauses_all_risk_levels(self, mock_generate):
        """Test extraction with all three risk levels."""
        db = AsyncMock()
        document_id = uuid.uuid4()
        
        chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                chunk_index=i,
                page_number=1,
                text=f"Clause {i} with payment terms.",
                token_count=50,
                embedding=None,
            )
            for i in range(3)
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = chunks
        async def mock_execute(*args, **kwargs):
            return mock_result
        db.execute = mock_execute
        
        # Mock response with low, medium, high risk
        from app.services.llm_orchestration import GroundedResponse
        mock_response = GroundedResponse(
            task="extract_clauses",
            content=f'[{{"clause_type": "payment_terms", "text_excerpt": "Clause 0", "start_offset": 0, "end_offset": 7, "chunk_id": "{chunks[0].id}", "risk_level": "low", "risk_rationale": "Standard terms."}}, {{"clause_type": "payment_terms", "text_excerpt": "Clause 1", "start_offset": 0, "end_offset": 7, "chunk_id": "{chunks[1].id}", "risk_level": "medium", "risk_rationale": "Some concerns."}}, {{"clause_type": "payment_terms", "text_excerpt": "Clause 2", "start_offset": 0, "end_offset": 7, "chunk_id": "{chunks[2].id}", "risk_level": "high", "risk_rationale": "Significant issues."}}]',
            citations=[],
            model_used="claude-haiku-4-5-20251001",
        )
        mock_generate.return_value = mock_response
        
        clauses = await extract_clauses_from_document(
            db=db,
            document_id=document_id,
            clause_type="payment_terms",
        )
        
        assert len(clauses) == 3
        risk_levels = {c.risk_level for c in clauses}
        assert risk_levels == {"low", "medium", "high"}

    @patch("app.services.clause_extraction.generate_grounded_response")
    async def test_extract_clauses_handles_llm_error(self, mock_generate):
        """Handle LLM generation errors gracefully."""
        db = AsyncMock()
        document_id = uuid.uuid4()
        
        chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                chunk_index=0,
                page_number=1,
                text="Client shall indemnify Provider.",
                token_count=50,
                embedding=None,
            ),
        ]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = chunks
        async def mock_execute(*args, **kwargs):
            return mock_result
        db.execute = mock_execute
        
        mock_generate.side_effect = ValueError("LLM generation failed")
        
        with pytest.raises(ValueError, match="LLM generation failed"):
            await extract_clauses_from_document(
                db=db,
                document_id=document_id,
                clause_type="indemnification",
            )


class TestClauseCandidate:
    """Test ClauseCandidate data structure."""

    def test_clause_candidate_creation(self):
        """Create valid ClauseCandidate."""
        chunk_id = uuid.uuid4()
        
        from app.services.clause_extraction import ClauseCandidate
        candidate = ClauseCandidate(
            clause_type="termination",
            text_excerpt="Either party may terminate",
            start_offset=0,
            end_offset=26,
            chunk_id=chunk_id,
            risk_level="low",
            risk_rationale="Mutual termination rights.",
        )
        
        assert candidate.clause_type == "termination"
        assert candidate.risk_level == "low"
        assert candidate.chunk_id == chunk_id

    def test_clause_candidate_validates_risk_level(self):
        """Risk level must be low, medium, or high."""
        with pytest.raises(ValueError):
            from app.services.clause_extraction import ClauseCandidate
            ClauseCandidate(
                clause_type="termination",
                text_excerpt="text",
                start_offset=0,
                end_offset=4,
                chunk_id=uuid.uuid4(),
                risk_level="critical",  # Invalid
                risk_rationale="test",
            )
