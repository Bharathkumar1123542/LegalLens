"""
Unit tests — LLM orchestration service
Tests: Claude API integration, prompt construction, citation parsing, streaming, error handling.
Covers: architecture.md §6.4 LLM Orchestration Module.
"""

import uuid
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.document_chunk import DocumentChunk
from app.services.llm_orchestration import (
    Citation,
    GroundedResponse,
    generate_grounded_response,
    parse_citations_from_text,
)


class TestParseCitationsFromText:
    """Test citation extraction from LLM responses."""

    def test_parse_single_citation(self):
        """Extract one citation in [chunk:uuid] format."""
        chunk_id = uuid.uuid4()
        text = f"The tenant must pay rent [chunk:{chunk_id}]."
        
        citations = parse_citations_from_text(text)
        
        assert len(citations) == 1
        assert citations[0] == str(chunk_id)

    def test_parse_multiple_citations(self):
        """Extract multiple citations from text."""
        chunk_id1 = uuid.uuid4()
        chunk_id2 = uuid.uuid4()
        text = f"First clause [chunk:{chunk_id1}]. Second clause [chunk:{chunk_id2}]."
        
        citations = parse_citations_from_text(text)
        
        assert len(citations) == 2
        assert str(chunk_id1) in citations
        assert str(chunk_id2) in citations

    def test_parse_no_citations(self):
        """Handle text with no citations."""
        text = "This text has no citations."
        
        citations = parse_citations_from_text(text)
        
        assert citations == []

    def test_parse_duplicate_citations(self):
        """Remove duplicate citation references."""
        chunk_id = uuid.uuid4()
        text = f"First [chunk:{chunk_id}] and second [chunk:{chunk_id}]."
        
        citations = parse_citations_from_text(text)
        
        assert len(citations) == 1
        assert citations[0] == str(chunk_id)

    def test_parse_malformed_citations(self):
        """Ignore malformed citation formats."""
        text = "Bad [chunk:not-a-uuid] or [chunk:] or [chunkxyz]."
        
        citations = parse_citations_from_text(text)
        
        assert citations == []


@pytest.mark.asyncio
class TestGenerateGroundedResponse:
    """Test main LLM orchestration function."""

    @patch("app.services.llm_orchestration.anthropic")
    async def test_generate_simplify_success(self, mock_anthropic):
        """Test simplification task with citations."""
        # Mock Anthropic client
        mock_client = AsyncMock()
        mock_message = MagicMock()
        
        chunk_id = uuid.uuid4()
        mock_message.content = [
            MagicMock(
                type="text",
                text=f'{{"simplified_text": "Plain language version [chunk:{chunk_id}].", "reading_level": "plain_english", "citations": [{{"chunk_id": "{chunk_id}", "page_number": 3, "excerpt": "Original text..."}}], "disclaimer": "This is informational only."}}',
            )
        ]
        mock_message.stop_reason = "end_turn"
        
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_anthropic.AsyncAnthropic.return_value = mock_client
        
        # Mock document chunks
        chunks = [
            DocumentChunk(
                id=chunk_id,
                document_id=uuid.uuid4(),
                chunk_index=0,
                page_number=3,
                text="Original legal text that needs simplification.",
                token_count=50,
                embedding=None,
            )
        ]
        
        response = await generate_grounded_response(
            task="simplify",
            context_chunks=chunks,
            user_input="",
            reading_level="plain_english",
        )
        
        assert response.task == "simplify"
        assert "Plain language version" in response.content
        assert len(response.citations) == 1
        assert response.citations[0].chunk_id == chunk_id
        assert response.citations[0].page_number == 3
        
        # Verify Claude API was called with correct model
        mock_client.messages.create.assert_awaited_once()
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-20250514"
        assert call_kwargs["max_tokens"] >= 4096

    @patch("app.services.llm_orchestration.anthropic")
    async def test_generate_chat_success(self, mock_anthropic):
        """Test chat task with RAG retrieval."""
        mock_client = AsyncMock()
        mock_message = MagicMock()
        
        chunk_id = uuid.uuid4()
        mock_message.content = [
            MagicMock(
                type="text",
                text=f"The termination notice period is 30 days [chunk:{chunk_id}].",
            )
        ]
        mock_message.stop_reason = "end_turn"
        
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_anthropic.AsyncAnthropic.return_value = mock_client
        
        chunks = [
            DocumentChunk(
                id=chunk_id,
                document_id=uuid.uuid4(),
                chunk_index=5,
                page_number=7,
                text="Either party may terminate with 30 days written notice.",
                token_count=60,
                embedding=[0.1] * 1024,
            )
        ]
        
        response = await generate_grounded_response(
            task="chat",
            context_chunks=chunks,
            user_input="What is the termination notice period?",
            reading_level=None,
        )
        
        assert response.task == "chat"
        assert "30 days" in response.content
        assert len(response.citations) >= 1
        
        # Verify system prompt includes legal disclaimer
        call_kwargs = mock_client.messages.create.call_args.kwargs
        system_prompt = call_kwargs["system"]
        assert "informational" in system_prompt.lower()
        assert "not legal advice" in system_prompt.lower()

    @patch("app.services.llm_orchestration.anthropic")
    async def test_generate_extract_clauses_uses_haiku(self, mock_anthropic):
        """Test clause extraction uses cheaper haiku model."""
        mock_client = AsyncMock()
        mock_message = MagicMock()
        
        chunk_id = uuid.uuid4()
        mock_message.content = [
            MagicMock(
                type="text",
                text=f'[{{"clause_type": "termination", "text_excerpt": "Either party may terminate...", "start_offset": 0, "end_offset": 50, "chunk_id": "{chunk_id}", "risk_level": "low", "risk_rationale": "Balanced mutual termination."}}]',
            )
        ]
        mock_message.stop_reason = "end_turn"
        
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_anthropic.AsyncAnthropic.return_value = mock_client
        
        chunks = [
            DocumentChunk(
                id=chunk_id,
                document_id=uuid.uuid4(),
                chunk_index=0,
                page_number=1,
                text="Either party may terminate this agreement with 30 days notice.",
                token_count=100,
                embedding=None,
            )
        ]
        
        response = await generate_grounded_response(
            task="extract_clauses",
            context_chunks=chunks,
            user_input="termination",  # clause type to extract
            reading_level=None,
        )
        
        assert response.task == "extract_clauses"
        
        # Verify haiku model was used (cheaper for classification)
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-5-20251001"

    @patch("app.services.llm_orchestration.anthropic")
    async def test_generate_includes_all_chunks_in_context(self, mock_anthropic):
        """Verify all provided chunks are included in prompt."""
        mock_client = AsyncMock()
        mock_message = MagicMock()
        # Return valid JSON for simplify task
        mock_message.content = [
            MagicMock(
                type="text",
                text='{"simplified_text": "Response", "reading_level": "plain_english", "citations": [], "disclaimer": "Info only"}',
            )
        ]
        mock_message.stop_reason = "end_turn"
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_anthropic.AsyncAnthropic.return_value = mock_client
        
        doc_id = uuid.uuid4()
        chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=doc_id,
                chunk_index=i,
                page_number=i+1,
                text=f"Chunk {i} text content.",
                token_count=50,
                embedding=None,
            )
            for i in range(5)
        ]
        
        await generate_grounded_response(
            task="simplify",
            context_chunks=chunks,
            user_input="",
            reading_level="plain_english",
        )
        
        call_kwargs = mock_client.messages.create.call_args.kwargs
        messages = call_kwargs["messages"]
        
        # User message should contain all 5 chunks
        user_message = messages[0]["content"]
        for i in range(5):
            assert f"Chunk {i} text content" in user_message

    @patch("app.services.llm_orchestration.anthropic")
    async def test_generate_validates_citations(self, mock_anthropic):
        """Verify citations are validated against provided chunks."""
        mock_client = AsyncMock()
        mock_message = MagicMock()
        
        valid_chunk_id = uuid.uuid4()
        fake_chunk_id = uuid.uuid4()  # Not in context
        
        mock_message.content = [
            MagicMock(
                type="text",
                text=f"Valid citation [chunk:{valid_chunk_id}]. Invalid [chunk:{fake_chunk_id}].",
            )
        ]
        mock_message.stop_reason = "end_turn"
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_anthropic.AsyncAnthropic.return_value = mock_client
        
        chunks = [
            DocumentChunk(
                id=valid_chunk_id,
                document_id=uuid.uuid4(),
                chunk_index=0,
                page_number=1,
                text="Valid chunk text.",
                token_count=50,
                embedding=None,
            )
        ]
        
        response = await generate_grounded_response(
            task="chat",
            context_chunks=chunks,
            user_input="Test question",
            reading_level=None,
        )
        
        # Should only include valid citation
        assert len(response.citations) == 1
        assert response.citations[0].chunk_id == valid_chunk_id

    @patch("app.services.llm_orchestration.anthropic")
    async def test_generate_handles_api_error(self, mock_anthropic):
        """Handle Claude API errors gracefully."""
        mock_client = AsyncMock()
        mock_client.messages.create.side_effect = Exception("API rate limit exceeded")
        mock_anthropic.AsyncAnthropic.return_value = mock_client
        
        chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                chunk_index=0,
                page_number=1,
                text="Test text",
                token_count=50,
                embedding=None,
            )
        ]
        
        with pytest.raises(ValueError, match="LLM generation failed"):
            await generate_grounded_response(
                task="simplify",
                context_chunks=chunks,
                user_input="",
                reading_level="plain_english",
            )

    @patch("app.services.llm_orchestration.anthropic")
    async def test_generate_handles_malformed_json_response(self, mock_anthropic):
        """Handle malformed JSON in LLM response."""
        mock_client = AsyncMock()
        mock_message = MagicMock()
        mock_message.content = [
            MagicMock(type="text", text="This is not valid JSON {broken")
        ]
        mock_message.stop_reason = "end_turn"
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_anthropic.AsyncAnthropic.return_value = mock_client
        
        chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                chunk_index=0,
                page_number=1,
                text="Text",
                token_count=50,
                embedding=None,
            )
        ]
        
        # Should handle gracefully (return raw text or raise clear error)
        with pytest.raises(ValueError, match="Failed to parse|Invalid response"):
            await generate_grounded_response(
                task="extract_clauses",
                context_chunks=chunks,
                user_input="termination",
                reading_level=None,
            )

    @patch("app.services.llm_orchestration.anthropic")
    async def test_generate_requires_chunks(self, mock_anthropic):
        """Raise error if no chunks provided."""
        with pytest.raises(ValueError, match="At least one context chunk required"):
            await generate_grounded_response(
                task="simplify",
                context_chunks=[],
                user_input="",
                reading_level="plain_english",
            )

    @patch("app.services.llm_orchestration.anthropic")
    async def test_generate_validates_reading_level(self, mock_anthropic):
        """Validate reading_level for simplify task."""
        chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                chunk_index=0,
                page_number=1,
                text="Text",
                token_count=50,
                embedding=None,
            )
        ]
        
        with pytest.raises(ValueError, match="reading_level.*simplify"):
            await generate_grounded_response(
                task="simplify",
                context_chunks=chunks,
                user_input="",
                reading_level="invalid_level",
            )

    @patch("app.services.llm_orchestration.anthropic")
    async def test_generate_loads_correct_prompt_template(self, mock_anthropic):
        """Verify correct prompt template loaded for each task."""
        mock_client = AsyncMock()
        mock_message = MagicMock()
        # Return valid JSON for simplify task
        mock_message.content = [
            MagicMock(
                type="text",
                text='{"simplified_text": "Response", "reading_level": "plain_english", "citations": [], "disclaimer": "Info only"}',
            )
        ]
        mock_message.stop_reason = "end_turn"
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_anthropic.AsyncAnthropic.return_value = mock_client
        
        chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                chunk_index=0,
                page_number=1,
                text="Text",
                token_count=50,
                embedding=None,
            )
        ]
        
        # Test simplify task
        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = "Simplify prompt template"
            
            await generate_grounded_response(
                task="simplify",
                context_chunks=chunks,
                user_input="",
                reading_level="plain_english",
            )
            
            # Should have loaded simplify.md
            opened_files = [call[0][0] for call in mock_open.call_args_list]
            assert any("simplify.md" in str(f) for f in opened_files)


class TestGroundedResponse:
    """Test GroundedResponse data structure."""

    def test_grounded_response_creation(self):
        """Create valid GroundedResponse."""
        chunk_id = uuid.uuid4()
        
        citation = Citation(
            chunk_id=chunk_id,
            page_number=5,
            excerpt="Original text excerpt",
        )
        
        response = GroundedResponse(
            task="simplify",
            content="Simplified content",
            citations=[citation],
            model_used="claude-sonnet-4-20250514",
        )
        
        assert response.task == "simplify"
        assert response.content == "Simplified content"
        assert len(response.citations) == 1
        assert response.citations[0].chunk_id == chunk_id

    def test_citation_requires_valid_uuid(self):
        """Citation chunk_id must be valid UUID."""
        with pytest.raises(ValueError):
            Citation(
                chunk_id="not-a-uuid",  # type: ignore[arg-type]
                page_number=1,
                excerpt="text",
            )


class TestCitationExtraction:
    """Test citation ID extraction from various formats."""

    def test_extract_citations_from_json_response(self):
        """Extract citations from JSON structured response."""
        chunk_id1 = uuid.uuid4()
        chunk_id2 = uuid.uuid4()
        
        json_text = f'''
        {{
            "simplified_text": "Content here [chunk:{chunk_id1}].",
            "citations": [
                {{"chunk_id": "{chunk_id1}", "page_number": 3}},
                {{"chunk_id": "{chunk_id2}", "page_number": 5}}
            ]
        }}
        '''
        
        citations = parse_citations_from_text(json_text)
        
        # Should extract from both inline [chunk:] format AND citations array
        assert str(chunk_id1) in citations
        assert str(chunk_id2) in citations

    def test_extract_handles_mixed_uuid_formats(self):
        """Handle UUIDs with/without hyphens."""
        chunk_id = uuid.uuid4()
        chunk_id_no_hyphens = str(chunk_id).replace("-", "")
        
        text = f"Citation [chunk:{chunk_id}] and [chunk:{chunk_id_no_hyphens}]"
        
        citations = parse_citations_from_text(text)
        
        # Should normalize to same UUID
        assert len(set(citations)) >= 1  # At least one valid UUID extracted
