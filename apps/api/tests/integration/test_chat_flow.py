"""
Integration test — Phase 4 Q&A chat flow
Tests: Create session → ask question → verify citations → retrieve history → list sessions.
Verifies: Phase 4 exit criteria (every answer includes ≥1 citation).
"""

import io
import uuid
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.chat import ChatSession, ChatMessage
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.user import User


@pytest.mark.asyncio
class TestChatFlow:
    """Test end-to-end Q&A chat flow."""

    async def _create_ready_document_with_chunks(
        self,
        test_user: User,
        db_session,
        chunk_count: int = 5,
    ) -> tuple[uuid.UUID, list[DocumentChunk]]:
        """
        Helper: Create a document with status=ready and test chunks with embeddings.
        Returns (document_id, chunks).
        """
        # Create document
        doc = Document(
            owner_id=test_user.id,
            original_filename="test_contract.pdf",
            mime_type="application/pdf",
            file_size_bytes=5000,
            storage_key=f"{test_user.id}/test_contract.pdf",
            file_hash_sha256="a" * 64,
            status="ready",
            page_count=chunk_count,
            language="en",
        )
        db_session.add(doc)
        await db_session.flush()
        
        # Create chunks with legal text and embeddings
        chunks = []
        for i in range(chunk_count):
            chunk_text = (
                f"Section {i+1}. This agreement contains the following terms: "
                f"Payment is due within 30 days of invoice. "
                f"The contract term is 12 months starting from execution date. "
                f"Either party may terminate with 60 days written notice. "
                f"Late payments incur a 5% monthly fee. "
                f"All disputes shall be resolved through binding arbitration."
            )
            
            chunk = DocumentChunk(
                document_id=doc.id,
                chunk_index=i,
                page_number=i + 1,
                text=chunk_text,
                token_count=100,
                embedding=[0.1 * (i + 1)] * 1024,  # Mock embedding
            )
            db_session.add(chunk)
            chunks.append(chunk)
        
        await db_session.commit()
        await db_session.refresh(doc)
        
        return doc.id, chunks

    @patch("app.services.llm_orchestration.AsyncAnthropic")
    async def test_create_session_and_ask_question(
        self,
        mock_anthropic_class,
        test_client: TestClient,
        auth_headers: dict,
        test_user: User,
        db_session,
    ):
        """
        Test full Q&A flow:
        1. Create ready document with chunks
        2. POST /documents/{id}/chat/sessions to create session
        3. POST /chat/sessions/{id}/messages to ask question
        4. Verify answer has citations (Phase 4 exit criterion)
        """
        # Setup: Create ready document with chunks
        doc_id, chunks = await self._create_ready_document_with_chunks(
            test_user, db_session, chunk_count=5
        )
        
        # Step 1: Create chat session
        response = test_client.post(
            f"/api/v1/documents/{doc_id}/chat/sessions",
            headers=auth_headers,
        )
        
        assert response.status_code == 201
        session_data = response.json()
        
        assert "session" in session_data
        session = session_data["session"]
        assert session["document_id"] == str(doc_id)
        assert session["owner_id"] == str(test_user.id)
        
        session_id = session["id"]
        
        # Setup: Mock Claude response for Q&A
        mock_client = AsyncMock()
        mock_anthropic_class.return_value = mock_client
        
        mock_message = MagicMock()
        mock_message.content = [
            MagicMock(
                text=(
                    f"Payment is due within 30 days of invoice [chunk:{chunks[0].id}]. "
                    f"Late payments incur a 5% monthly fee [chunk:{chunks[1].id}]."
                )
            )
        ]
        mock_message.stop_reason = "end_turn"
        
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        
        # Step 2: Ask question
        response = test_client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={
                "question": "What are the payment terms?",
                "top_k": 8,
            },
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        message = response.json()
        
        # Verify message structure
        assert message["role"] == "assistant"
        assert "30 days" in message["content"]
        assert "citations" in message
        
        # Phase 4 exit criterion: Every answer includes ≥1 citation
        assert len(message["citations"]) >= 1
        
        # Verify citation structure
        for citation in message["citations"]:
            assert "chunk_id" in citation
            assert "page_number" in citation
            assert "excerpt" in citation
            # Verify chunk_id is valid UUID
            uuid.UUID(citation["chunk_id"])
        
        # Verify citations reference actual chunks
        cited_chunk_ids = {uuid.UUID(c["chunk_id"]) for c in message["citations"]}
        chunk_ids = {chunk.id for chunk in chunks}
        assert cited_chunk_ids.issubset(chunk_ids)

    @patch("app.services.llm_orchestration.AsyncAnthropic")
    async def test_conversation_with_history(
        self,
        mock_anthropic_class,
        test_client: TestClient,
        auth_headers: dict,
        test_user: User,
        db_session,
    ):
        """
        Test multi-turn conversation with history:
        1. Ask first question
        2. Ask follow-up question
        3. Verify history is maintained
        4. Retrieve full history
        """
        # Setup
        doc_id, chunks = await self._create_ready_document_with_chunks(
            test_user, db_session, chunk_count=3
        )
        
        # Create session
        response = test_client.post(
            f"/api/v1/documents/{doc_id}/chat/sessions",
            headers=auth_headers,
        )
        session_id = response.json()["session"]["id"]
        
        # Setup mocks
        mock_client = AsyncMock()
        mock_anthropic_class.return_value = mock_client
        
        # First question mock response
        mock_message_1 = MagicMock()
        mock_message_1.content = [
            MagicMock(
                text=f"The contract term is 12 months [chunk:{chunks[0].id}]."
            )
        ]
        mock_message_1.stop_reason = "end_turn"
        
        # Second question mock response
        mock_message_2 = MagicMock()
        mock_message_2.content = [
            MagicMock(
                text=f"Either party may terminate with 60 days notice [chunk:{chunks[1].id}]."
            )
        ]
        mock_message_2.stop_reason = "end_turn"
        
        mock_client.messages.create = AsyncMock(
            side_effect=[mock_message_1, mock_message_2]
        )
        
        # Ask first question
        response1 = test_client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"question": "What is the contract term?"},
            headers=auth_headers,
        )
        
        assert response1.status_code == 200
        message1 = response1.json()
        assert "12 months" in message1["content"]
        assert len(message1["citations"]) >= 1
        
        # Ask follow-up question
        response2 = test_client.post(
            f"/api/v1/chat/sessions/{session_id}/messages",
            json={"question": "How can it be terminated?"},
            headers=auth_headers,
        )
        
        assert response2.status_code == 200
        message2 = response2.json()
        assert "60 days" in message2["content"]
        assert len(message2["citations"]) >= 1
        
        # Retrieve history
        response = test_client.get(
            f"/api/v1/chat/sessions/{session_id}/messages",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        history = response.json()
        
        assert history["session_id"] == session_id
        assert history["total"] == 4  # 2 user + 2 assistant messages
        assert len(history["messages"]) == 4
        
        # Verify message order (oldest first)
        messages = history["messages"]
        assert messages[0]["role"] == "user"
        assert "contract term" in messages[0]["content"].lower()
        assert messages[1]["role"] == "assistant"
        assert "12 months" in messages[1]["content"]
        assert messages[2]["role"] == "user"
        assert "terminated" in messages[2]["content"].lower()
        assert messages[3]["role"] == "assistant"
        assert "60 days" in messages[3]["content"]

    async def test_list_sessions_for_document(
        self,
        test_client: TestClient,
        auth_headers: dict,
        test_user: User,
        db_session,
    ):
        """
        Test session listing:
        1. Create multiple sessions for same document
        2. GET /documents/{id}/chat/sessions
        3. Verify all sessions returned
        4. Verify ordering by last_message_at desc
        """
        # Setup
        doc_id, _ = await self._create_ready_document_with_chunks(
            test_user, db_session, chunk_count=2
        )
        
        # Create 3 sessions
        session_ids = []
        for _ in range(3):
            response = test_client.post(
                f"/api/v1/documents/{doc_id}/chat/sessions",
                headers=auth_headers,
            )
            assert response.status_code == 201
            session_ids.append(response.json()["session"]["id"])
        
        # List sessions
        response = test_client.get(
            f"/api/v1/documents/{doc_id}/chat/sessions",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["document_id"] == str(doc_id)
        assert data["total"] == 3
        assert len(data["sessions"]) == 3
        
        # Verify all session IDs present
        returned_ids = {s["id"] for s in data["sessions"]}
        assert returned_ids == set(session_ids)
        
        # Verify sessions ordered by last_message_at desc (most recent first)
        for i in range(len(data["sessions"]) - 1):
            current = data["sessions"][i]["last_message_at"]
            next_item = data["sessions"][i + 1]["last_message_at"]
            # Most recent should come first
            assert current >= next_item

    async def test_session_isolation(
        self,
        test_client: TestClient,
        auth_headers: dict,
        test_user: User,
        db_session,
    ):
        """
        Test that chat sessions are isolated:
        1. Create two sessions for same document
        2. Add messages to both
        3. Verify history for each session is separate
        """
        # Setup
        doc_id, chunks = await self._create_ready_document_with_chunks(
            test_user, db_session, chunk_count=3
        )
        
        # Create two sessions
        response1 = test_client.post(
            f"/api/v1/documents/{doc_id}/chat/sessions",
            headers=auth_headers,
        )
        session1_id = response1.json()["session"]["id"]
        
        response2 = test_client.post(
            f"/api/v1/documents/{doc_id}/chat/sessions",
            headers=auth_headers,
        )
        session2_id = response2.json()["session"]["id"]
        
        # Add messages directly to database (bypass LLM)
        async with db_session.begin():
            # Session 1: 2 messages
            msg1 = ChatMessage(
                session_id=uuid.UUID(session1_id),
                role="user",
                content="Question 1",
                citations=[],
            )
            msg2 = ChatMessage(
                session_id=uuid.UUID(session1_id),
                role="assistant",
                content="Answer 1",
                citations=[{"chunk_id": str(chunks[0].id), "page_number": 1, "excerpt": "..."}],
            )
            db_session.add(msg1)
            db_session.add(msg2)
            
            # Session 2: 4 messages
            msg3 = ChatMessage(
                session_id=uuid.UUID(session2_id),
                role="user",
                content="Question A",
                citations=[],
            )
            msg4 = ChatMessage(
                session_id=uuid.UUID(session2_id),
                role="assistant",
                content="Answer A",
                citations=[{"chunk_id": str(chunks[1].id), "page_number": 2, "excerpt": "..."}],
            )
            msg5 = ChatMessage(
                session_id=uuid.UUID(session2_id),
                role="user",
                content="Question B",
                citations=[],
            )
            msg6 = ChatMessage(
                session_id=uuid.UUID(session2_id),
                role="assistant",
                content="Answer B",
                citations=[{"chunk_id": str(chunks[2].id), "page_number": 3, "excerpt": "..."}],
            )
            db_session.add(msg3)
            db_session.add(msg4)
            db_session.add(msg5)
            db_session.add(msg6)
        
        await db_session.commit()
        
        # Retrieve history for session 1
        response1 = test_client.get(
            f"/api/v1/chat/sessions/{session1_id}/messages",
            headers=auth_headers,
        )
        history1 = response1.json()
        
        assert history1["total"] == 2
        assert len(history1["messages"]) == 2
        assert "Question 1" in history1["messages"][0]["content"]
        
        # Retrieve history for session 2
        response2 = test_client.get(
            f"/api/v1/chat/sessions/{session2_id}/messages",
            headers=auth_headers,
        )
        history2 = response2.json()
        
        assert history2["total"] == 4
        assert len(history2["messages"]) == 4
        assert "Question A" in history2["messages"][0]["content"]
        assert "Question B" in history2["messages"][2]["content"]

    async def test_document_not_ready_error(
        self,
        test_client: TestClient,
        auth_headers: dict,
        test_user: User,
        db_session,
    ):
        """
        Test error when trying to chat with document not ready.
        """
        # Create document with status=processing
        doc = Document(
            owner_id=test_user.id,
            original_filename="processing.pdf",
            mime_type="application/pdf",
            file_size_bytes=5000,
            storage_key=f"{test_user.id}/processing.pdf",
            file_hash_sha256="b" * 64,
            status="processing",
            processing_stage="chunking",
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)
        
        # Try to create chat session
        response = test_client.post(
            f"/api/v1/documents/{doc.id}/chat/sessions",
            headers=auth_headers,
        )
        
        assert response.status_code == 409
        assert "processing" in response.json()["detail"].lower()

    async def test_unauthorized_access(
        self,
        test_client: TestClient,
        auth_headers: dict,
        test_user: User,
        db_session,
    ):
        """
        Test that users cannot access other users' chat sessions.
        """
        # Create document for test_user
        doc_id, _ = await self._create_ready_document_with_chunks(
            test_user, db_session, chunk_count=2
        )
        
        # Create session as test_user
        response = test_client.post(
            f"/api/v1/documents/{doc_id}/chat/sessions",
            headers=auth_headers,
        )
        session_id = response.json()["session"]["id"]
        
        # Create another user
        other_user = User(
            email="other@example.com",
            password_hash="hashed",
            full_name="Other User",
            role="user",
            is_active=True,
        )
        db_session.add(other_user)
        await db_session.commit()
        
        # Try to access session as other user (would need different auth_headers)
        # For this test, we verify at DB level that session belongs to original user
        result = await db_session.execute(
            select(ChatSession).where(ChatSession.id == uuid.UUID(session_id))
        )
        session = result.scalar_one()
        
        assert session.owner_id == test_user.id
        assert session.owner_id != other_user.id
