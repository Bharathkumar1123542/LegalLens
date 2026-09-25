"""
E2E tests — Complete user journey (Phase 0-5)
Tests: Full workflow from registration → upload → process → simplify → extract → chat → compare → export
Covers: End-to-end user scenarios with all major features
"""

import io
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.clause import Clause
from app.models.chat import ChatMessage
from app.models.comparison import ComparisonJob, ComparisonResult
from app.models.export import ExportArtifact


@pytest.mark.asyncio
class TestCompleteUserJourney:
    """Test complete user workflows from start to finish."""

    @patch("app.services.storage.upload_to_s3")
    @patch("app.services.ingestion.extract_text_from_pdf")
    @patch("app.services.llm_orchestration.AsyncAnthropic")
    async def test_full_document_workflow(
        self,
        mock_anthropic_class,
        mock_extract_text,
        mock_upload_s3,
        async_client,
        db_session: AsyncSession,
        test_user,
        auth_headers: dict,
    ):
        """
        Complete workflow: Register → Upload → Process → Simplify → Extract → Chat
        
        Steps:
        1. User registers (use test_user fixture)
        2. Upload PDF document
        3. Document processing (ingestion worker)
        4. Simplify document
        5. Extract clauses
        6. Chat about document
        """
        # Step 1: User already registered (test_user fixture)
        assert test_user.email == "testuser@example.com"
        
        # Step 2: Upload document
        mock_upload_s3.return_value = AsyncMock()
        
        pdf_content = b"%PDF-1.4 test content"
        files = {"file": ("contract.pdf", io.BytesIO(pdf_content), "application/pdf")}
        
        upload_response = await async_client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=auth_headers,
        )
        
        assert upload_response.status_code == 201
        doc_data = upload_response.json()
        doc_id = doc_data["id"]
        assert doc_data["status"] == "uploaded"
        assert doc_data["original_filename"] == "contract.pdf"
        
        # Step 3: Process document (simulate worker)
        mock_extract_text.return_value = """
        EMPLOYMENT AGREEMENT
        
        This agreement governs the employment relationship.
        
        TERMINATION: Either party may terminate with 30 days notice.
        
        CONFIDENTIALITY: Employee must maintain confidentiality of company information.
        
        PAYMENT: Salary payable monthly on the last business day.
        """
        
        # Simulate ingestion worker
        result = await db_session.execute(
            select(Document).where(Document.id == uuid.UUID(doc_id))
        )
        doc = result.scalar_one()
        
        from app.services.ingestion import process_document
        await process_document(db=db_session, document_id=doc.id)
        
        # Verify document processed
        await db_session.refresh(doc)
        assert doc.status == "ready"
        assert doc.plaintext_content is not None
        
        # Step 4: Simplify document
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=json.dumps({
            "simplified_text": "This is an employment contract. You can quit with 30 days notice. Keep company secrets. Get paid monthly.",
            "reading_level_grade": 8.0,
            "key_terms": ["employment", "termination", "confidentiality", "payment"],
            "citations": [{"original": "30 days notice", "location": "Section 2"}],
        }))]
        
        mock_client = AsyncMock()
        mock_client.messages.create.return_value = mock_message
        mock_anthropic_class.return_value = mock_client
        
        simplify_response = await async_client.post(
            f"/api/v1/documents/{doc_id}/simplify",
            json={"reading_level": "8th_grade"},
            headers=auth_headers,
        )
        
        assert simplify_response.status_code == 200
        simplify_data = simplify_response.json()
        assert "simplified_text" in simplify_data
        assert simplify_data["reading_level_grade"] == 8.0
        
        # Step 5: Extract clauses
        mock_message2 = MagicMock()
        mock_message2.content = [MagicMock(text=json.dumps({
            "clauses": [
                {
                    "clause_type": "termination",
                    "text_excerpt": "Either party may terminate with 30 days notice",
                    "risk_level": "medium",
                    "risk_rationale": "Short notice period may not allow adequate transition time",
                },
                {
                    "clause_type": "confidentiality",
                    "text_excerpt": "Employee must maintain confidentiality of company information",
                    "risk_level": "low",
                    "risk_rationale": "Standard confidentiality requirement",
                },
            ]
        }))]
        
        mock_client.messages.create.return_value = mock_message2
        
        extract_response = await async_client.post(
            f"/api/v1/documents/{doc_id}/extract-clauses",
            headers=auth_headers,
        )
        
        assert extract_response.status_code == 202  # Accepted
        
        # Simulate extraction worker
        from app.services.clause_extraction import extract_clauses
        await extract_clauses(db=db_session, document_id=doc.id)
        
        # Verify clauses extracted
        clauses_result = await db_session.execute(
            select(Clause).where(Clause.document_id == doc.id)
        )
        clauses = clauses_result.scalars().all()
        assert len(clauses) >= 2
        assert any(c.clause_type == "termination" for c in clauses)
        
        # Step 6: Chat about document
        mock_message3 = MagicMock()
        mock_message3.content = [MagicMock(text="The termination clause requires 30 days notice from either party. This is a standard provision but may not provide enough time for transition planning.")]
        
        mock_client.messages.create.return_value = mock_message3
        
        chat_response = await async_client.post(
            f"/api/v1/chat/{doc_id}",
            json={"message": "What does the termination clause say?"},
            headers=auth_headers,
        )
        
        assert chat_response.status_code == 201
        chat_data = chat_response.json()
        assert "30 days notice" in chat_data["response"]
        
        # Verify chat message saved
        messages_result = await db_session.execute(
            select(ChatMessage).where(ChatMessage.document_id == doc.id)
        )
        messages = messages_result.scalars().all()
        assert len(messages) == 2  # User message + assistant response
    
    @patch("app.services.storage.upload_to_s3")
    @patch("app.services.ingestion.extract_text_from_pdf")
    @patch("app.services.llm_orchestration.AsyncAnthropic")
    @patch("app.services.export.render_to_pdf")
    async def test_comparison_and_export_workflow(
        self,
        mock_render_pdf,
        mock_anthropic_class,
        mock_extract_text,
        mock_upload_s3,
        async_client,
        db_session: AsyncSession,
        test_user,
        auth_headers: dict,
    ):
        """
        Complete comparison workflow: Upload 2 docs → Compare → Export report
        
        Steps:
        1. Upload two contract versions
        2. Process both documents
        3. Extract clauses from both
        4. Create comparison job
        5. Run comparison
        6. Export comparison report
        """
        mock_upload_s3.return_value = AsyncMock()
        mock_extract_text.return_value = "Contract text with clauses..."
        
        # Step 1-2: Upload and process 2 documents
        doc_ids = []
        
        for i, filename in enumerate(["contract_v1.pdf", "contract_v2.pdf"]):
            # Upload
            files = {"file": (filename, io.BytesIO(b"%PDF test"), "application/pdf")}
            upload_resp = await async_client.post(
                "/api/v1/documents/upload",
                files=files,
                headers=auth_headers,
            )
            assert upload_resp.status_code == 201
            doc_id = upload_resp.json()["id"]
            doc_ids.append(doc_id)
            
            # Process
            result = await db_session.execute(
                select(Document).where(Document.id == uuid.UUID(doc_id))
            )
            doc = result.scalar_one()
            
            from app.services.ingestion import process_document
            await process_document(db=db_session, document_id=doc.id)
            
            await db_session.refresh(doc)
            assert doc.status == "ready"
        
        # Step 3: Extract clauses from both documents
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=json.dumps({
            "clauses": [
                {
                    "clause_type": "payment_terms",
                    "text_excerpt": f"Payment {'Net 30' if i == 0 else 'Net 60'}",
                    "risk_level": "low",
                    "risk_rationale": "Standard payment terms",
                },
                {
                    "clause_type": "liability",
                    "text_excerpt": f"Liability {'capped at $10k' if i == 0 else 'unlimited'}",
                    "risk_level": "low" if i == 0 else "high",
                    "risk_rationale": "Liability provision",
                },
            ]
        }))]
        
        mock_client = AsyncMock()
        mock_client.messages.create.return_value = mock_message
        mock_anthropic_class.return_value = mock_client
        
        for doc_id in doc_ids:
            result = await db_session.execute(
                select(Document).where(Document.id == uuid.UUID(doc_id))
            )
            doc = result.scalar_one()
            
            from app.services.clause_extraction import extract_clauses
            await extract_clauses(db=db_session, document_id=doc.id)
        
        # Verify clauses exist
        for doc_id in doc_ids:
            clauses_result = await db_session.execute(
                select(Clause).where(Clause.document_id == uuid.UUID(doc_id))
            )
            clauses = clauses_result.scalars().all()
            assert len(clauses) >= 2
        
        # Step 4: Create comparison
        comparison_resp = await async_client.post(
            "/api/v1/comparisons",
            json={"document_ids": doc_ids},
            headers=auth_headers,
        )
        
        assert comparison_resp.status_code == 201
        comparison_data = comparison_resp.json()
        job_id = comparison_data["id"]
        assert comparison_data["status"] == "queued"
        
        # Step 5: Run comparison (simulate worker)
        mock_comparison_message = MagicMock()
        mock_comparison_message.content = [MagicMock(text=json.dumps({
            "clause_type": "payment_terms",
            "diff_summary": "Document 2 allows 30 extra days for payment (Net 60 vs Net 30)",
            "materiality": "minor",
        }))]
        
        mock_client.messages.create.side_effect = [
            mock_comparison_message,
            MagicMock(content=[MagicMock(text=json.dumps({
                "clause_type": "liability",
                "diff_summary": "Document 2 has unlimited liability vs $10k cap in document 1",
                "materiality": "critical",
            }))]),
        ]
        
        from app.services.comparison import run_comparison
        await run_comparison(db=db_session, comparison_job_id=uuid.UUID(job_id))
        
        # Verify comparison completed
        job_result = await db_session.execute(
            select(ComparisonJob).where(ComparisonJob.id == uuid.UUID(job_id))
        )
        job = job_result.scalar_one()
        assert job.status == "completed"
        
        # Verify results
        results_query = await db_session.execute(
            select(ComparisonResult).where(
                ComparisonResult.comparison_job_id == uuid.UUID(job_id)
            )
        )
        results = results_query.scalars().all()
        assert len(results) == 2
        
        # Step 6: Export comparison report
        export_resp = await async_client.post(
            "/api/v1/exports",
            json={
                "comparison_job_id": job_id,
                "export_type": "comparison_report",
                "file_format": "pdf",
            },
            headers=auth_headers,
        )
        
        assert export_resp.status_code == 201
        export_data = export_resp.json()
        export_id = export_data["id"]
        assert export_data["status"] == "queued"
        
        # Simulate export worker
        mock_render_pdf.return_value = io.BytesIO(b"PDF comparison report")
        
        from app.services.export import generate_export
        storage_key, file_size = await generate_export(
            db=db_session,
            export_id=uuid.UUID(export_id),
        )
        
        # Verify export ready
        export_result = await db_session.execute(
            select(ExportArtifact).where(ExportArtifact.id == uuid.UUID(export_id))
        )
        export_artifact = export_result.scalar_one()
        assert export_artifact.status == "ready"
        assert export_artifact.storage_key is not None
        
        # Get export with download URL
        get_export_resp = await async_client.get(
            f"/api/v1/exports/{export_id}",
            headers=auth_headers,
        )
        
        assert get_export_resp.status_code == 200
        final_export_data = get_export_resp.json()
        assert final_export_data["status"] == "ready"
        assert "download_url" in final_export_data
    
    @patch("app.services.storage.upload_to_s3")
    @patch("app.services.ingestion.extract_text_from_pdf")
    @patch("app.services.llm_orchestration.AsyncAnthropic")
    @patch("app.services.export.render_to_docx")
    async def test_multi_export_workflow(
        self,
        mock_render_docx,
        mock_anthropic_class,
        mock_extract_text,
        mock_upload_s3,
        async_client,
        db_session: AsyncSession,
        test_user,
        auth_headers: dict,
    ):
        """
        Test exporting same document in multiple formats.
        
        Steps:
        1. Upload and process document
        2. Extract clauses
        3. Export as summary (PDF)
        4. Export as checklist (DOCX)
        5. Export as lawyer brief (Markdown)
        """
        mock_upload_s3.return_value = AsyncMock()
        mock_extract_text.return_value = "Legal document with various clauses..."
        
        # Step 1: Upload and process
        files = {"file": ("agreement.pdf", io.BytesIO(b"%PDF test"), "application/pdf")}
        upload_resp = await async_client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=auth_headers,
        )
        
        doc_id = upload_resp.json()["id"]
        
        result = await db_session.execute(
            select(Document).where(Document.id == uuid.UUID(doc_id))
        )
        doc = result.scalar_one()
        
        from app.services.ingestion import process_document
        await process_document(db=db_session, document_id=doc.id)
        
        # Step 2: Extract clauses
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=json.dumps({
            "clauses": [
                {
                    "clause_type": "termination",
                    "text_excerpt": "7 day termination notice",
                    "risk_level": "high",
                    "risk_rationale": "Very short notice period",
                },
                {
                    "clause_type": "warranty",
                    "text_excerpt": "90 day warranty",
                    "risk_level": "medium",
                    "risk_rationale": "Limited warranty period",
                },
            ]
        }))]
        
        mock_client = AsyncMock()
        mock_client.messages.create.return_value = mock_message
        mock_anthropic_class.return_value = mock_client
        
        from app.services.clause_extraction import extract_clauses
        await extract_clauses(db=db_session, document_id=doc.id)
        
        # Step 3-5: Create multiple exports
        export_configs = [
            {"export_type": "summary", "file_format": "pdf"},
            {"export_type": "checklist", "file_format": "docx"},
            {"export_type": "lawyer_brief", "file_format": "md"},
        ]
        
        export_ids = []
        
        for config in export_configs:
            export_resp = await async_client.post(
                "/api/v1/exports",
                json={
                    "document_id": doc_id,
                    **config,
                },
                headers=auth_headers,
            )
            
            assert export_resp.status_code == 201
            export_data = export_resp.json()
            export_ids.append(export_data["id"])
            assert export_data["export_type"] == config["export_type"]
            assert export_data["file_format"] == config["file_format"]
        
        # Verify all exports created
        assert len(export_ids) == 3
        
        # Verify in database
        exports_result = await db_session.execute(
            select(ExportArtifact).where(
                ExportArtifact.document_id == doc.id
            )
        )
        exports = exports_result.scalars().all()
        assert len(exports) == 3
        
        export_types = {e.export_type for e in exports}
        assert export_types == {"summary", "checklist", "lawyer_brief"}
    
    async def test_unauthorized_access_blocked(
        self,
        async_client,
        db_session: AsyncSession,
        test_user,
        another_user,
        auth_headers: dict,
        other_auth_headers: dict,
    ):
        """
        Verify ownership enforcement across entire workflow.
        
        Test that user cannot access another user's:
        - Documents
        - Clauses
        - Chat messages
        - Comparisons
        - Exports
        """
        # Create document owned by test_user
        doc = Document(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            original_filename="private.pdf",
            mime_type="application/pdf",
            file_size_bytes=1000,
            storage_key=f"{test_user.id}/private.pdf",
            file_hash_sha256="a" * 64,
            status="ready",
        )
        db_session.add(doc)
        await db_session.commit()
        
        # Try to access with another_user - should fail
        get_doc_resp = await async_client.get(
            f"/api/v1/documents/{doc.id}",
            headers=other_auth_headers,
        )
        assert get_doc_resp.status_code == 404
        
        # Try to simplify - should fail
        simplify_resp = await async_client.post(
            f"/api/v1/documents/{doc.id}/simplify",
            json={"reading_level": "8th_grade"},
            headers=other_auth_headers,
        )
        assert simplify_resp.status_code == 404
        
        # Try to chat - should fail
        chat_resp = await async_client.post(
            f"/api/v1/chat/{doc.id}",
            json={"message": "Test"},
            headers=other_auth_headers,
        )
        assert chat_resp.status_code == 404
        
        # Create comparison owned by test_user
        job = ComparisonJob(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            status="completed",
        )
        db_session.add(job)
        await db_session.commit()
        
        # Try to access comparison - should fail
        comparison_resp = await async_client.get(
            f"/api/v1/comparisons/{job.id}",
            headers=other_auth_headers,
        )
        assert comparison_resp.status_code == 404
        
        # Create export owned by test_user
        export_artifact = ExportArtifact(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            document_id=doc.id,
            export_type="summary",
            file_format="pdf",
            status="ready",
        )
        db_session.add(export_artifact)
        await db_session.commit()
        
        # Try to access export - should fail
        export_resp = await async_client.get(
            f"/api/v1/exports/{export_artifact.id}",
            headers=other_auth_headers,
        )
        assert export_resp.status_code == 404


@pytest.mark.asyncio
class TestErrorRecoveryJourney:
    """Test error handling and recovery in user workflows."""

    async def test_upload_invalid_file_type(
        self,
        async_client,
        auth_headers: dict,
    ):
        """Reject non-PDF/DOCX file uploads."""
        files = {"file": ("image.jpg", io.BytesIO(b"fake image"), "image/jpeg")}
        
        response = await async_client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=auth_headers,
        )
        
        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]
    
    async def test_simplify_before_processing_complete(
        self,
        async_client,
        db_session: AsyncSession,
        test_user,
        auth_headers: dict,
    ):
        """Cannot simplify document still processing."""
        doc = Document(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            original_filename="processing.pdf",
            mime_type="application/pdf",
            file_size_bytes=1000,
            storage_key=f"{test_user.id}/processing.pdf",
            file_hash_sha256="a" * 64,
            status="processing",  # Not ready yet
        )
        db_session.add(doc)
        await db_session.commit()
        
        response = await async_client.post(
            f"/api/v1/documents/{doc.id}/simplify",
            json={"reading_level": "8th_grade"},
            headers=auth_headers,
        )
        
        assert response.status_code == 400
        assert "not ready" in response.json()["detail"].lower()
    
    async def test_compare_documents_different_owners(
        self,
        async_client,
        db_session: AsyncSession,
        test_user,
        another_user,
        auth_headers: dict,
    ):
        """Cannot compare documents from different users."""
        doc1 = Document(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            original_filename="mine.pdf",
            mime_type="application/pdf",
            file_size_bytes=1000,
            storage_key=f"{test_user.id}/mine.pdf",
            file_hash_sha256="a" * 64,
            status="ready",
        )
        doc2 = Document(
            id=uuid.uuid4(),
            owner_id=another_user.id,
            original_filename="theirs.pdf",
            mime_type="application/pdf",
            file_size_bytes=1000,
            storage_key=f"{another_user.id}/theirs.pdf",
            file_hash_sha256="b" * 64,
            status="ready",
        )
        db_session.add(doc1)
        db_session.add(doc2)
        await db_session.commit()
        
        response = await async_client.post(
            "/api/v1/comparisons",
            json={"document_ids": [str(doc1.id), str(doc2.id)]},
            headers=auth_headers,
        )
        
        assert response.status_code == 400
        assert "not owned" in response.json()["detail"].lower()
