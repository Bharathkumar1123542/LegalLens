"""
Integration test — Phase 3 simplification & clause extraction flow
Tests: Document upload → ready → simplify → extract clauses → retrieve clauses.
Verifies: Phase 3 exit criteria (architecture.md §3, §6).
"""

import io
import uuid
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.clause import Clause
from app.models.user import User


@pytest.mark.asyncio
class TestPhase3Flow:
    """Test end-to-end simplification and clause extraction."""

    async def _create_ready_document_with_chunks(
        self,
        test_user: User,
        db_session,
        chunk_count: int = 3,
    ) -> tuple[uuid.UUID, list[DocumentChunk]]:
        """
        Helper: Create a document with status=ready and test chunks.
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
        
        # Create chunks with legal text
        chunks = []
        for i in range(chunk_count):
            chunk_text = (
                f"Chunk {i+1}. This agreement contains indemnification provisions. "
                f"The party agrees to indemnify and hold harmless all losses. "
                f"Payment terms require net 30 days. "
                f"This agreement may be terminated with 60 days notice. "
                f"Confidential information must not be disclosed. "
            )
            
            chunk = DocumentChunk(
                document_id=doc.id,
                chunk_index=i,
                page_number=i + 1,
                text=chunk_text,
                token_count=100,
            )
            db_session.add(chunk)
            chunks.append(chunk)
        
        await db_session.commit()
        await db_session.refresh(doc)
        
        return doc.id, chunks

    @patch("app.services.llm_orchestration.AsyncAnthropic")
    async def test_simplification_end_to_end(
        self,
        mock_anthropic_class,
        test_client: TestClient,
        auth_headers: dict,
        test_user: User,
        db_session,
    ):
        """
        Test full simplification flow:
        1. Create ready document with chunks
        2. POST /documents/{id}/simplify
        3. Verify simplified text with citations
        """
        # Setup: Create ready document
        doc_id, chunks = await self._create_ready_document_with_chunks(
            test_user, db_session, chunk_count=3
        )
        
        # Mock Claude response for simplification
        mock_client = AsyncMock()
        mock_anthropic_class.return_value = mock_client
        
        mock_message = MagicMock()
        mock_message.content = [
            MagicMock(
                text=(
                    "This agreement has protection rules [chunk:" + str(chunks[0].id) + "]. "
                    "You must pay within 30 days [chunk:" + str(chunks[1].id) + "]. "
                    "Either party can end the agreement [chunk:" + str(chunks[2].id) + "]."
                )
            )
        ]
        mock_message.stop_reason = "end_turn"
        
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        
        # Act: Simplify document
        response = test_client.post(
            f"/api/v1/documents/{doc_id}/simplify",
            json={"reading_level": "elementary"},
            headers=auth_headers,
        )
        
        # Assert: Response structure
        assert response.status_code == 200
        data = response.json()
        
        assert data["document_id"] == str(doc_id)
        assert data["reading_level"] == "elementary"
        assert "simplified_text" in data
        assert len(data["simplified_text"]) > 0
        assert "citations" in data
        assert len(data["citations"]) == 3  # One per chunk
        assert data["chunk_count"] == 3
        
        # Verify disclaimer present
        assert "not a substitute for legal advice" in data["disclaimer"].lower()
        
        # Verify citations structure
        for citation in data["citations"]:
            assert "chunk_id" in citation
            assert "page_number" in citation
            assert citation["page_number"] in [1, 2, 3]

    @patch("app.services.llm_orchestration.AsyncAnthropic")
    async def test_clause_extraction_end_to_end(
        self,
        mock_anthropic_class,
        test_client: TestClient,
        auth_headers: dict,
        test_user: User,
        db_session,
    ):
        """
        Test full clause extraction flow:
        1. Create ready document with chunks
        2. POST /documents/{id}/extract-clauses (async)
        3. Run worker synchronously
        4. GET /documents/{id}/clauses
        5. Verify ≥3 clause types extracted with risk levels
        """
        # Setup: Create ready document
        doc_id, chunks = await self._create_ready_document_with_chunks(
            test_user, db_session, chunk_count=3
        )
        
        # Mock Claude responses for clause classification
        mock_client = AsyncMock()
        mock_anthropic_class.return_value = mock_client
        
        # Create mock responses for different clause types
        def create_clause_response(clause_type: str, risk: str):
            return MagicMock(
                content=[
                    MagicMock(
                        text=(
                            '{"clauses": [{'
                            f'"clause_type": "{clause_type}", '
                            f'"text_excerpt": "Sample {clause_type} clause text", '
                            '"start_offset": 0, '
                            '"end_offset": 50, '
                            f'"risk_level": "{risk}", '
                            f'"risk_rationale": "This {clause_type} clause poses {risk} risk."'
                            "}]}"
                        )
                    )
                ],
                stop_reason="end_turn",
            )
        
        # Queue responses for multiple clause types
        mock_client.messages.create = AsyncMock(
            side_effect=[
                create_clause_response("indemnification", "high"),
                create_clause_response("termination", "medium"),
                create_clause_response("payment_terms", "low"),
                create_clause_response("confidentiality", "medium"),
            ]
        )
        
        # Act: Request clause extraction
        response = test_client.post(
            f"/api/v1/documents/{doc_id}/extract-clauses",
            json={
                "clause_types": [
                    "indemnification",
                    "termination",
                    "payment_terms",
                    "confidentiality",
                ]
            },
            headers=auth_headers,
        )
        
        # Assert: 202 Accepted
        assert response.status_code == 202
        data = response.json()
        assert data["document_id"] == str(doc_id)
        assert len(data["clause_types"]) == 4
        
        # Simulate worker execution (synchronous for testing)
        from app.workers.clause_extraction_worker import _extract_clauses_async
        
        result = await _extract_clauses_async(
            document_id=doc_id,
            clause_types=[
                "indemnification",
                "termination",
                "payment_terms",
                "confidentiality",
            ],
        )
        
        # Verify worker results
        assert result["total_extracted"] == 4
        assert result["by_type"]["indemnification"] == 1
        assert result["by_type"]["termination"] == 1
        assert result["by_type"]["payment_terms"] == 1
        assert result["by_type"]["confidentiality"] == 1
        
        # Act: Retrieve extracted clauses
        response = test_client.get(
            f"/api/v1/documents/{doc_id}/clauses",
            headers=auth_headers,
        )
        
        # Assert: Clauses retrieved successfully
        assert response.status_code == 200
        data = response.json()
        
        assert data["document_id"] == str(doc_id)
        assert data["total"] == 4
        assert len(data["clauses"]) == 4
        
        # Verify statistics
        assert data["by_type"]["indemnification"] == 1
        assert data["by_type"]["termination"] == 1
        assert data["by_type"]["payment_terms"] == 1
        assert data["by_type"]["confidentiality"] == 1
        
        assert data["by_risk"]["high"] == 1
        assert data["by_risk"]["medium"] == 2
        assert data["by_risk"]["low"] == 1
        
        # Verify clause structure
        for clause in data["clauses"]:
            assert "id" in clause
            assert "clause_type" in clause
            assert clause["clause_type"] in [
                "indemnification",
                "termination",
                "payment_terms",
                "confidentiality",
            ]
            assert "risk_level" in clause
            assert clause["risk_level"] in ["low", "medium", "high"]
            assert "risk_rationale" in clause
            assert "text_excerpt" in clause
            assert "start_offset" in clause
            assert "end_offset" in clause
            assert clause["end_offset"] > clause["start_offset"]

    @patch("app.services.llm_orchestration.AsyncAnthropic")
    async def test_clause_filtering(
        self,
        mock_anthropic_class,
        test_client: TestClient,
        auth_headers: dict,
        test_user: User,
        db_session,
    ):
        """
        Test clause retrieval with filters:
        1. Extract multiple clauses with different types/risks
        2. Filter by clause_type
        3. Filter by risk_level
        """
        # Setup: Create ready document
        doc_id, chunks = await self._create_ready_document_with_chunks(
            test_user, db_session, chunk_count=3
        )
        
        # Create test clauses directly in DB
        clauses_data = [
            ("indemnification", "high"),
            ("indemnification", "medium"),
            ("termination", "low"),
            ("payment_terms", "medium"),
        ]
        
        for clause_type, risk_level in clauses_data:
            clause = Clause(
                document_id=doc_id,
                source_chunk_id=chunks[0].id,
                clause_type=clause_type,
                text_excerpt=f"Sample {clause_type} text",
                start_offset=0,
                end_offset=50,
                risk_level=risk_level,
                risk_rationale=f"{risk_level.capitalize()} risk clause",
            )
            db_session.add(clause)
        
        await db_session.commit()
        
        # Test 1: Filter by clause_type
        response = test_client.get(
            f"/api/v1/documents/{doc_id}/clauses?clause_type=indemnification",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2  # 2 indemnification clauses
        assert all(c["clause_type"] == "indemnification" for c in data["clauses"])
        
        # Test 2: Filter by risk_level
        response = test_client.get(
            f"/api/v1/documents/{doc_id}/clauses?risk_level=medium",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2  # 2 medium risk clauses
        assert all(c["risk_level"] == "medium" for c in data["clauses"])
        
        # Test 3: No filters (all clauses)
        response = test_client.get(
            f"/api/v1/documents/{doc_id}/clauses",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 4  # All 4 clauses

    async def test_document_not_ready_error(
        self,
        test_client: TestClient,
        auth_headers: dict,
        test_user: User,
        db_session,
    ):
        """
        Test error handling when document is not ready:
        - Simplify: should return 409
        - Extract clauses: should return 409
        """
        # Create document with status=processing
        doc = Document(
            owner_id=test_user.id,
            original_filename="processing.pdf",
            mime_type="application/pdf",
            file_size_bytes=5000,
            storage_key=f"{test_user.id}/processing.pdf",
            file_hash_sha256="b" * 64,
            status="processing",  # Not ready
            processing_stage="chunking",
        )
        db_session.add(doc)
        await db_session.commit()
        await db_session.refresh(doc)
        
        # Test simplify endpoint
        response = test_client.post(
            f"/api/v1/documents/{doc.id}/simplify",
            json={"reading_level": "plain_english"},
            headers=auth_headers,
        )
        
        assert response.status_code == 409
        assert "processing" in response.json()["detail"].lower()
        
        # Test extract clauses endpoint
        response = test_client.post(
            f"/api/v1/documents/{doc.id}/extract-clauses",
            json={"clause_types": ["indemnification"]},
            headers=auth_headers,
        )
        
        assert response.status_code == 409
        assert "processing" in response.json()["detail"].lower()
