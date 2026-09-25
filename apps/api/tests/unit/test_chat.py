"""
Unit tests — Chat service (Phase 4)
Tests: start_chat_session(), ask_question() with RAG retrieval, citations.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatSession, ChatMessage
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.user import User


@pytest.fixture
def test_user():
    """Test user fixture."""
    return User(
        id=uuid.uuid4(),
        email="test@example.com",
        password_hash="hashed",
        full_name="Test User",
        role="user",
        is_active=True,
    )


@pytest.fixture
def test_document(test_user):
    """Test document fixture with status=ready."""
    return Document(
        id=uuid.uuid4(),
        owner_id=test_user.id,
        original_filename="contract.pdf",
        mime_type="application/pdf",
        file_size_bytes=5000,
        storage_key=f"{test_user.id}/contract.pdf",
        file_hash_sha256="a" * 64,
        status="ready",
        page_count=3,
        language="en",
    )


@pytest.fixture
def test_chunks(test_document):
    """Test document chunks with text and embeddings."""
    chunks = []
    for i in range(3):
        chunk = DocumentChunk(
            id=uuid.uuid4(),
            document_id=test_document.id,
            chunk_index=i,
            page_number=i + 1,
            text=f"Chunk {i+1} contains important legal text about payments and termination.",
            token_count=50,
            embedding=[0.1] * 1024,  # Mock embedding
        )
        chunks.append(chunk)
    return chunks


@pytest.mark.asyncio
class TestChatSessionManagement:
    """Test chat session creation and management."""
    
    async def test_start_chat_session_success(self, test_user, test_document):
        """Test successful chat session creation."""
        from app.services.chat import start_chat_session
        
        # Mock database
        db = AsyncMock(spec=AsyncSession)
        
        # Mock document query
        mock_doc_result = MagicMock()
        mock_doc_result.scalar_one_or_none.return_value = test_document
        
        async def mock_execute_doc(*args, **kwargs):
            return mock_doc_result
        
        db.execute = mock_execute_doc
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        
        # Call service
        session = await start_chat_session(
            db=db,
            document_id=test_document.id,
            owner_id=test_user.id,
        )
        
        # Assertions
        assert session is not None
        assert session.document_id == test_document.id
        assert session.owner_id == test_user.id
        db.add.assert_called_once()
        db.commit.assert_called_once()
    
    async def test_start_chat_session_document_not_found(self, test_user):
        """Test error when document doesn't exist."""
        from app.services.chat import start_chat_session
        
        db = AsyncMock(spec=AsyncSession)
        
        # Mock document not found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        
        async def mock_execute(*args, **kwargs):
            return mock_result
        
        db.execute = mock_execute
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Document .* not found"):
            await start_chat_session(
                db=db,
                document_id=uuid.uuid4(),
                owner_id=test_user.id,
            )
    
    async def test_start_chat_session_document_not_ready(self, test_user):
        """Test error when document status != ready."""
        from app.services.chat import start_chat_session
        
        db = AsyncMock(spec=AsyncSession)
        
        # Mock document with status=processing
        processing_doc = Document(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            original_filename="processing.pdf",
            mime_type="application/pdf",
            file_size_bytes=5000,
            storage_key=f"{test_user.id}/processing.pdf",
            file_hash_sha256="b" * 64,
            status="processing",
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = processing_doc
        
        async def mock_execute(*args, **kwargs):
            return mock_result
        
        db.execute = mock_execute
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="status is 'processing'"):
            await start_chat_session(
                db=db,
                document_id=processing_doc.id,
                owner_id=test_user.id,
            )


@pytest.mark.asyncio
class TestAskQuestion:
    """Test ask_question with RAG retrieval."""
    
    @patch("app.services.chat.retrieve_relevant_chunks")
    @patch("app.services.chat.generate_grounded_response")
    async def test_ask_question_success(
        self,
        mock_generate,
        mock_retrieve,
        test_user,
        test_document,
        test_chunks,
    ):
        """Test successful question answering with citations."""
        from app.services.chat import ask_question
        
        # Setup mocks
        db = AsyncMock(spec=AsyncSession)
        
        # Mock session query
        session = ChatSession(
            id=uuid.uuid4(),
            document_id=test_document.id,
            owner_id=test_user.id,
            created_at=datetime.now(timezone.utc),
            last_message_at=datetime.now(timezone.utc),
        )
        
        mock_session_result = MagicMock()
        mock_session_result.scalar_one_or_none.return_value = session
        
        # Mock message history query
        mock_history_result = MagicMock()
        mock_history_result.scalars.return_value.all.return_value = []
        
        call_count = [0]
        
        async def mock_execute(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:  # First call: session query
                return mock_session_result
            else:  # Second call: history query
                return mock_history_result
        
        db.execute = mock_execute
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        
        # Mock retrieval
        mock_retrieve.return_value = test_chunks[:2]  # Top 2 chunks
        
        # Mock LLM generation
        from app.services.llm_orchestration import GroundedResponse, Citation
        
        mock_generate.return_value = GroundedResponse(
            text=f"Payment is due within 30 days [chunk:{test_chunks[0].id}].",
            citations=[
                Citation(
                    chunk_id=test_chunks[0].id,
                    page_number=1,
                    excerpt="Payment terms: net 30 days",
                )
            ],
        )
        
        # Call service
        message = await ask_question(
            db=db,
            session_id=session.id,
            document_id=test_document.id,
            question="What are the payment terms?",
        )
        
        # Assertions
        assert message is not None
        assert message.role == "assistant"
        assert "30 days" in message.content
        assert len(message.citations) == 1
        assert message.citations[0]["chunk_id"] == str(test_chunks[0].id)
        
        # Verify retrieval was called
        mock_retrieve.assert_called_once()
        
        # Verify LLM was called
        mock_generate.assert_called_once()
    
    @patch("app.services.chat.retrieve_relevant_chunks")
    @patch("app.services.chat.generate_grounded_response")
    async def test_ask_question_with_history(
        self,
        mock_generate,
        mock_retrieve,
        test_user,
        test_document,
        test_chunks,
    ):
        """Test question answering includes conversation history."""
        from app.services.chat import ask_question
        
        db = AsyncMock(spec=AsyncSession)
        
        # Mock session
        session = ChatSession(
            id=uuid.uuid4(),
            document_id=test_document.id,
            owner_id=test_user.id,
            created_at=datetime.now(timezone.utc),
            last_message_at=datetime.now(timezone.utc),
        )
        
        # Mock history with previous messages
        prev_user_msg = ChatMessage(
            id=uuid.uuid4(),
            session_id=session.id,
            role="user",
            content="What are the payment terms?",
            citations=[],
            created_at=datetime.now(timezone.utc),
        )
        
        prev_assistant_msg = ChatMessage(
            id=uuid.uuid4(),
            session_id=session.id,
            role="assistant",
            content="Payment is due within 30 days.",
            citations=[{"chunk_id": str(test_chunks[0].id), "page_number": 1, "excerpt": "..."}],
            created_at=datetime.now(timezone.utc),
        )
        
        mock_session_result = MagicMock()
        mock_session_result.scalar_one_or_none.return_value = session
        
        mock_history_result = MagicMock()
        mock_history_result.scalars.return_value.all.return_value = [
            prev_user_msg,
            prev_assistant_msg,
        ]
        
        call_count = [0]
        
        async def mock_execute(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_session_result
            else:
                return mock_history_result
        
        db.execute = mock_execute
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        
        mock_retrieve.return_value = test_chunks[:2]
        
        from app.services.llm_orchestration import GroundedResponse, Citation
        
        mock_generate.return_value = GroundedResponse(
            text=f"Late fees apply after the payment period [chunk:{test_chunks[1].id}].",
            citations=[
                Citation(
                    chunk_id=test_chunks[1].id,
                    page_number=2,
                    excerpt="Late fee: 5% per month",
                )
            ],
        )
        
        # Ask follow-up question
        message = await ask_question(
            db=db,
            session_id=session.id,
            document_id=test_document.id,
            question="What about late fees?",
        )
        
        # Verify history was passed to LLM
        call_args = mock_generate.call_args
        assert "history" in call_args.kwargs or len(call_args.args) >= 5
        
        assert message.role == "assistant"
        assert len(message.citations) == 1
    
    async def test_ask_question_session_not_found(self, test_document):
        """Test error when session doesn't exist."""
        from app.services.chat import ask_question
        
        db = AsyncMock(spec=AsyncSession)
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        
        async def mock_execute(*args, **kwargs):
            return mock_result
        
        db.execute = mock_execute
        
        with pytest.raises(ValueError, match="Chat session .* not found"):
            await ask_question(
                db=db,
                session_id=uuid.uuid4(),
                document_id=test_document.id,
                question="Test question",
            )
    
    @patch("app.services.chat.retrieve_relevant_chunks")
    async def test_ask_question_no_relevant_chunks(
        self,
        mock_retrieve,
        test_user,
        test_document,
    ):
        """Test handling when no relevant chunks found."""
        from app.services.chat import ask_question
        
        db = AsyncMock(spec=AsyncSession)
        
        session = ChatSession(
            id=uuid.uuid4(),
            document_id=test_document.id,
            owner_id=test_user.id,
            created_at=datetime.now(timezone.utc),
            last_message_at=datetime.now(timezone.utc),
        )
        
        mock_session_result = MagicMock()
        mock_session_result.scalar_one_or_none.return_value = session
        
        mock_history_result = MagicMock()
        mock_history_result.scalars.return_value.all.return_value = []
        
        call_count = [0]
        
        async def mock_execute(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_session_result
            else:
                return mock_history_result
        
        db.execute = mock_execute
        
        # No chunks found
        mock_retrieve.return_value = []
        
        with pytest.raises(ValueError, match="No relevant context found"):
            await ask_question(
                db=db,
                session_id=session.id,
                document_id=test_document.id,
                question="Completely unrelated question",
            )


@pytest.mark.asyncio
class TestCitationValidation:
    """Test citation requirements for assistant messages."""
    
    @patch("app.services.chat.retrieve_relevant_chunks")
    @patch("app.services.chat.generate_grounded_response")
    async def test_assistant_message_requires_citations(
        self,
        mock_generate,
        mock_retrieve,
        test_user,
        test_document,
        test_chunks,
    ):
        """Test that assistant messages with factual claims have citations."""
        from app.services.chat import ask_question
        
        db = AsyncMock(spec=AsyncSession)
        
        session = ChatSession(
            id=uuid.uuid4(),
            document_id=test_document.id,
            owner_id=test_user.id,
            created_at=datetime.now(timezone.utc),
            last_message_at=datetime.now(timezone.utc),
        )
        
        mock_session_result = MagicMock()
        mock_session_result.scalar_one_or_none.return_value = session
        
        mock_history_result = MagicMock()
        mock_history_result.scalars.return_value.all.return_value = []
        
        call_count = [0]
        
        async def mock_execute(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_session_result
            else:
                return mock_history_result
        
        db.execute = mock_execute
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        
        mock_retrieve.return_value = test_chunks[:2]
        
        from app.services.llm_orchestration import GroundedResponse, Citation
        
        # LLM returns response with citations
        mock_generate.return_value = GroundedResponse(
            text=f"The contract term is 12 months [chunk:{test_chunks[0].id}].",
            citations=[
                Citation(
                    chunk_id=test_chunks[0].id,
                    page_number=1,
                    excerpt="Term: twelve (12) months",
                )
            ],
        )
        
        message = await ask_question(
            db=db,
            session_id=session.id,
            document_id=test_document.id,
            question="What is the contract term?",
        )
        
        # Per architecture.md §7.2:
        # citations required non-empty when role=assistant and answer makes factual claim
        assert len(message.citations) >= 1
        assert all(
            "chunk_id" in c and "page_number" in c and "excerpt" in c
            for c in message.citations
        )
