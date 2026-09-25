"""
Integration test — full ingestion pipeline
Tests: Upload → text extraction → chunking → embedding → status=ready.
Verifies: Phase 2 exit criteria (architecture.md, ai-workflow-rules.md).
"""

import io
import uuid
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.user import User


@pytest.mark.asyncio
class TestIngestionPipeline:
    """Test end-to-end document processing."""

    @patch("app.services.ingestion.upload_to_s3", new_callable=AsyncMock)
    @patch("app.services.ingestion.record_audit_event", new_callable=AsyncMock)
    @patch("app.workers.ingestion_worker.embed_chunks", new_callable=AsyncMock)
    @patch("app.services.text_extraction.fitz")
    async def test_pdf_upload_to_ready_with_chunks(
        self,
        mock_fitz,
        mock_embed,
        mock_audit,
        mock_s3,
        test_client: TestClient,
        auth_headers: dict,
        test_user: User,
        db_session,
    ):
        """
        Phase 2 exit criterion: 10-page PDF reaches status=ready with correctly ordered chunks.
        """
        # Mock PDF with 10 pages of text
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 10
        
        pages = []
        for i in range(10):
            mock_page = MagicMock()
            # Each page has ~200 words → ~1 chunk per page
            page_text = f"Page {i+1} content. " + "Legal text. " * 40
            mock_page.get_text.return_value = page_text
            pages.append(mock_page)
        
        mock_doc.__getitem__.side_effect = pages
        mock_fitz.open.return_value.__enter__.return_value = mock_doc
        
        # Upload PDF
        pdf_content = b"%PDF-1.4\n" + b"x" * 1000  # Fake PDF
        files = {"file": ("test_10page.pdf", io.BytesIO(pdf_content), "application/pdf")}
        
        response = test_client.post(
            "/api/v1/documents",
            files=files,
            headers=auth_headers,
        )
        
        assert response.status_code == 202
        doc_id = response.json()["id"]
        
        # Simulate Celery worker processing
        from app.workers.ingestion_worker import process_document_task
        
        # Mock S3 retrieval
        with patch("app.workers.ingestion_worker._s3_client") as mock_s3_client:
            mock_s3_obj = MagicMock()
            mock_s3_obj.get_object.return_value = {"Body": MagicMock(read=lambda: pdf_content)}
            mock_s3_client.return_value = mock_s3_obj
            
            # Run the worker task
            await process_document_task.run_async(process_document_task(), document_id=doc_id)
        
        # Verify document status
        result = await db_session.execute(
            select(Document).where(Document.id == uuid.UUID(doc_id))
        )
        doc = result.scalar_one()
        
        assert doc.status == "ready"
        assert doc.processing_stage is None
        assert doc.page_count == 10
        
        # Verify chunks were created
        chunks_result = await db_session.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == uuid.UUID(doc_id))
            .order_by(DocumentChunk.chunk_index)
        )
        chunks = chunks_result.scalars().all()
        
        # Should have ~10 chunks (1 per page for this content size)
        assert len(chunks) >= 8
        assert len(chunks) <= 15
        
        # Verify chunk ordering (chunk_index must be sequential)
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
        
        # Verify no overlapping chunks at same index
        chunk_indices = [c.chunk_index for c in chunks]
        assert len(chunk_indices) == len(set(chunk_indices))
        
        # Verify all chunks have page numbers
        for chunk in chunks:
            assert chunk.page_number is not None
            assert 1 <= chunk.page_number <= 10
        
        # Verify token counts are within bounds
        for chunk in chunks:
            assert chunk.token_count > 0
            assert chunk.token_count <= 700  # architecture.md §7.2 hard cap

    @patch("app.services.ingestion.upload_to_s3", new_callable=AsyncMock)
    @patch("app.services.ingestion.record_audit_event", new_callable=AsyncMock)
    @patch("app.workers.ingestion_worker.embed_chunks", new_callable=AsyncMock)
    @patch("app.services.text_extraction.Document")
    async def test_docx_upload_to_ready(
        self,
        mock_docx_class,
        mock_embed,
        mock_audit,
        mock_s3,
        test_client: TestClient,
        auth_headers: dict,
        db_session,
    ):
        """Test DOCX processing pipeline."""
        # Mock DOCX with several paragraphs
        mock_doc = MagicMock()
        paragraphs = [
            MagicMock(text=f"Paragraph {i}. " + "Content. " * 20)
            for i in range(5)
        ]
        mock_doc.paragraphs = paragraphs
        mock_docx_class.return_value = mock_doc
        
        # Upload DOCX
        docx_content = b"PK\x03\x04" + b"x" * 500  # Fake DOCX
        files = {"file": ("test.docx", io.BytesIO(docx_content), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        
        response = test_client.post(
            "/api/v1/documents",
            files=files,
            headers=auth_headers,
        )
        
        assert response.status_code == 202
        doc_id = response.json()["id"]
        
        # Simulate worker
        from app.workers.ingestion_worker import process_document_task
        
        with patch("app.workers.ingestion_worker._s3_client") as mock_s3_client:
            mock_s3_obj = MagicMock()
            mock_s3_obj.get_object.return_value = {"Body": MagicMock(read=lambda: docx_content)}
            mock_s3_client.return_value = mock_s3_obj
            
            await process_document_task.run_async(process_document_task(), document_id=doc_id)
        
        # Verify status
        result = await db_session.execute(
            select(Document).where(Document.id == uuid.UUID(doc_id))
        )
        doc = result.scalar_one()
        
        assert doc.status == "ready"
        assert doc.page_count is None  # DOCX has no pages
        
        # Verify chunks
        chunks_result = await db_session.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == uuid.UUID(doc_id))
        )
        chunks = chunks_result.scalars().all()
        
        assert len(chunks) >= 1
        # DOCX chunks should have no page_number
        for chunk in chunks:
            assert chunk.page_number is None

    @patch("app.services.ingestion.upload_to_s3", new_callable=AsyncMock)
    @patch("app.services.ingestion.record_audit_event", new_callable=AsyncMock)
    async def test_corrupted_file_marks_as_failed(
        self,
        mock_audit,
        mock_s3,
        test_client: TestClient,
        auth_headers: dict,
        db_session,
    ):
        """Test failure handling for corrupted files."""
        # Upload corrupted PDF
        corrupted_content = b"not a real pdf"
        files = {"file": ("corrupted.pdf", io.BytesIO(corrupted_content), "application/pdf")}
        
        response = test_client.post(
            "/api/v1/documents",
            files=files,
            headers=auth_headers,
        )
        
        assert response.status_code == 202
        doc_id = response.json()["id"]
        
        # Simulate worker processing
        from app.workers.ingestion_worker import process_document_task
        
        with patch("app.workers.ingestion_worker._s3_client") as mock_s3_client:
            mock_s3_obj = MagicMock()
            mock_s3_obj.get_object.return_value = {"Body": MagicMock(read=lambda: corrupted_content)}
            mock_s3_client.return_value = mock_s3_obj
            
            try:
                await process_document_task.run_async(process_document_task(), document_id=doc_id)
            except Exception:
                pass  # Expected to fail
        
        # Verify document marked as failed
        result = await db_session.execute(
            select(Document).where(Document.id == uuid.UUID(doc_id))
        )
        doc = result.scalar_one()
        
        assert doc.status == "failed"
        assert doc.failure_reason is not None
        assert "PDF" in doc.failure_reason or "parse" in doc.failure_reason.lower()
