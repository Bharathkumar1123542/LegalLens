"""
Unit tests — embedding service
Tests: Voyage AI integration, batch embedding, vector dimension validation, error handling.
Covers: architecture.md §6.3, §4 Voyage AI API.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.embedding import embed_chunks, embed_single_text, retrieve_relevant_chunks


class TestEmbedSingleText:
    """Test single text embedding via Voyage AI."""

    @patch("app.services.embedding.voyageai")
    def test_embed_single_text_success(self, mock_voyage):
        # Mock Voyage AI client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.embeddings = [[0.1] * 1024]  # 1024-dim vector
        mock_client.embed.return_value = mock_response
        mock_voyage.Client.return_value = mock_client
        
        text = "This is a test chunk of legal text."
        vector = embed_single_text(text)
        
        assert len(vector) == 1024
        assert all(isinstance(v, float) for v in vector)
        mock_client.embed.assert_called_once_with(
            [text],
            model="voyage-3",
            input_type="document",
        )

    @patch("app.services.embedding.voyageai")
    def test_embed_single_text_handles_api_error(self, mock_voyage):
        mock_client = MagicMock()
        mock_client.embed.side_effect = Exception("Voyage API error")
        mock_voyage.Client.return_value = mock_client
        
        with pytest.raises(ValueError, match="Embedding failed"):
            embed_single_text("text")

    @patch("app.services.embedding.voyageai")
    def test_embed_single_text_validates_dimension(self, mock_voyage):
        # API returns wrong dimension
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.embeddings = [[0.1] * 512]  # Wrong: should be 1024
        mock_client.embed.return_value = mock_response
        mock_voyage.Client.return_value = mock_client
        
        with pytest.raises(ValueError, match="Expected 1024 dimensions"):
            embed_single_text("text")


@pytest.mark.asyncio
class TestEmbedChunks:
    """Test batch embedding for document chunks."""

    @patch("app.services.embedding.voyageai")
    async def test_embed_chunks_success(self, mock_voyage):
        # Mock Voyage AI batch embedding
        mock_client = MagicMock()
        mock_response = MagicMock()
        # Return 3 embeddings
        mock_response.embeddings = [
            [0.1] * 1024,
            [0.2] * 1024,
            [0.3] * 1024,
        ]
        mock_client.embed.return_value = mock_response
        mock_voyage.Client.return_value = mock_client
        
        # Mock database
        db = AsyncMock()
        document_id = uuid.uuid4()
        
        # Mock existing chunks
        from app.models.document_chunk import DocumentChunk
        chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                chunk_index=i,
                text=f"Chunk {i} text",
                token_count=100,
                embedding=None,
            )
            for i in range(3)
        ]
        db.execute.return_value.scalars.return_value.all.return_value = chunks
        
        await embed_chunks(db=db, document_id=document_id)
        
        # Verify embeddings were written
        for chunk in chunks:
            assert chunk.embedding is not None
            assert len(chunk.embedding) == 1024
        
        db.commit.assert_awaited_once()

    @patch("app.services.embedding.voyageai")
    async def test_embed_chunks_handles_empty_chunks(self, mock_voyage):
        db = AsyncMock()
        db.execute.return_value.scalars.return_value.all.return_value = []
        
        document_id = uuid.uuid4()
        
        # Should not raise, just log warning
        await embed_chunks(db=db, document_id=document_id)
        
        db.commit.assert_not_awaited()

    @patch("app.services.embedding.voyageai")
    async def test_embed_chunks_batches_large_documents(self, mock_voyage):
        # Test batching for documents with >100 chunks
        mock_client = MagicMock()
        
        # First batch: 100 chunks
        mock_response1 = MagicMock()
        mock_response1.embeddings = [[0.1] * 1024] * 100
        
        # Second batch: 50 chunks
        mock_response2 = MagicMock()
        mock_response2.embeddings = [[0.2] * 1024] * 50
        
        mock_client.embed.side_effect = [mock_response1, mock_response2]
        mock_voyage.Client.return_value = mock_client
        
        db = AsyncMock()
        document_id = uuid.uuid4()
        
        from app.models.document_chunk import DocumentChunk
        chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                chunk_index=i,
                text=f"Chunk {i}",
                token_count=100,
                embedding=None,
            )
            for i in range(150)
        ]
        db.execute.return_value.scalars.return_value.all.return_value = chunks
        
        await embed_chunks(db=db, document_id=document_id)
        
        # Should have called embed twice (batches of 100)
        assert mock_client.embed.call_count == 2


@pytest.mark.asyncio
class TestRetrieveRelevantChunks:
    """Test vector similarity search."""

    async def test_retrieve_relevant_chunks_success(self):
        db = AsyncMock()
        document_id = uuid.uuid4()
        query = "What are the termination conditions?"
        
        # Mock query embedding
        query_vector = [0.5] * 1024
        
        # Mock retrieved chunks
        from app.models.document_chunk import DocumentChunk
        mock_chunks = [
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                chunk_index=5,
                page_number=3,
                text="Termination clause text...",
                token_count=200,
                embedding=[0.51] * 1024,  # Similar to query
            ),
            DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                chunk_index=12,
                page_number=7,
                text="Another relevant clause...",
                token_count=180,
                embedding=[0.49] * 1024,
            ),
        ]
        db.execute.return_value.scalars.return_value.all.return_value = mock_chunks
        
        with patch("app.services.embedding.embed_single_text", return_value=query_vector):
            chunks = await retrieve_relevant_chunks(
                db=db,
                document_id=document_id,
                query=query,
                top_k=2,
            )
        
        assert len(chunks) == 2
        assert chunks[0].text == "Termination clause text..."

    async def test_retrieve_relevant_chunks_returns_empty_for_no_embeddings(self):
        db = AsyncMock()
        db.execute.return_value.scalars.return_value.all.return_value = []
        
        document_id = uuid.uuid4()
        
        with patch("app.services.embedding.embed_single_text", return_value=[0.5] * 1024):
            chunks = await retrieve_relevant_chunks(
                db=db,
                document_id=document_id,
                query="test query",
                top_k=5,
            )
        
        assert chunks == []

    async def test_retrieve_relevant_chunks_validates_top_k(self):
        db = AsyncMock()
        document_id = uuid.uuid4()
        
        # top_k must be positive
        with pytest.raises(ValueError, match="top_k must be positive"):
            await retrieve_relevant_chunks(
                db=db,
                document_id=document_id,
                query="test",
                top_k=0,
            )
