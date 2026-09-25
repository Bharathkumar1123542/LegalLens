"""
Unit tests — services/ingestion.py
Tests: magic-byte validation, deduplication, size limits, S3 integration.
Covers: code-standards.md §Security (no extension-based validation).
"""

import io
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException, UploadFile

from app.services.ingestion import create_document, _detect_mime_type


class TestMagicByteDetection:
    """Test MIME type detection from file content."""

    def test_detect_pdf_from_magic_bytes(self):
        # PDF starts with %PDF
        pdf_header = b"%PDF-1.4\n..."
        assert _detect_mime_type(pdf_header) == "application/pdf"

    def test_detect_docx_from_magic_bytes(self):
        # DOCX is a ZIP file starting with PK\x03\x04
        docx_header = b"PK\x03\x04\x14\x00..."
        assert _detect_mime_type(docx_header) == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def test_detect_plain_text_from_utf8(self):
        text_header = b"This is plain text content with no binary markers."
        assert _detect_mime_type(text_header) == "text/plain"

    def test_reject_binary_with_nul_bytes(self):
        binary_header = b"Some text\x00binary"
        assert _detect_mime_type(binary_header) is None

    def test_reject_non_utf8(self):
        binary_header = b"\xff\xfe\x00Invalid UTF-8"
        assert _detect_mime_type(binary_header) is None

    def test_reject_unsupported_magic_bytes(self):
        # JPEG magic bytes
        jpeg_header = b"\xff\xd8\xff\xe0\x00\x10JFIF"
        assert _detect_mime_type(jpeg_header) is None


@pytest.mark.asyncio
class TestCreateDocument:
    """Test document upload and validation."""

    async def test_create_document_succeeds_with_valid_pdf(self):
        pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF"
        file = UploadFile(filename="test.pdf")
        file.read = AsyncMock(return_value=pdf_content)
        
        owner_id = uuid.uuid4()
        db = AsyncMock()
        # No existing document (deduplication check)
        db.execute = AsyncMock(return_value=AsyncMock(scalar_one_or_none=AsyncMock(return_value=None)))
        
        with patch("app.services.ingestion.upload_to_s3", new_callable=AsyncMock) as mock_s3, \
             patch("app.services.ingestion.record_audit_event", new_callable=AsyncMock):
            
            doc = await create_document(
                owner_id=owner_id,
                file=file,
                db=db,
                ip_address="127.0.0.1",
            )
        
        assert doc.owner_id == owner_id
        assert doc.mime_type == "application/pdf"
        assert doc.status == "uploaded"
        assert doc.file_size_bytes == len(pdf_content)
        assert len(doc.file_hash_sha256) == 64  # SHA-256 hex
        db.add.assert_called_once()
        db.flush.assert_awaited_once()
        mock_s3.assert_awaited_once()

    async def test_create_document_rejects_oversized_file(self):
        # File > 20 MB
        large_content = b"x" * (21 * 1024 * 1024)
        file = UploadFile(filename="huge.pdf")
        file.read = AsyncMock(return_value=large_content)
        
        db = AsyncMock()
        
        with pytest.raises(HTTPException) as exc_info:
            await create_document(
                owner_id=uuid.uuid4(),
                file=file,
                db=db,
            )
        
        assert exc_info.value.status_code == 413
        assert "20 MB" in exc_info.value.detail

    async def test_create_document_rejects_empty_file(self):
        file = UploadFile(filename="empty.pdf")
        file.read = AsyncMock(return_value=b"")
        
        db = AsyncMock()
        
        with pytest.raises(HTTPException) as exc_info:
            await create_document(
                owner_id=uuid.uuid4(),
                file=file,
                db=db,
            )
        
        assert exc_info.value.status_code == 400
        assert "empty" in exc_info.value.detail.lower()

    async def test_create_document_rejects_unsupported_mime_type(self):
        # JPEG magic bytes — not supported
        jpeg_content = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00..."
        file = UploadFile(filename="photo.jpg")
        file.read = AsyncMock(return_value=jpeg_content)
        
        db = AsyncMock()
        
        with pytest.raises(HTTPException) as exc_info:
            await create_document(
                owner_id=uuid.uuid4(),
                file=file,
                db=db,
            )
        
        assert exc_info.value.status_code == 400
        assert "unsupported" in exc_info.value.detail.lower()
        # code-standards.md: validation message must clarify it's content-based, not extension
        assert "file content" in exc_info.value.detail.lower()

    async def test_create_document_deduplicates_same_hash(self):
        # Same file uploaded twice by the same user
        pdf_content = b"%PDF-1.4\nSame content"
        existing_doc_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        
        # Mock: existing document found during dedup check
        from app.models.document import Document
        existing_doc = Document(
            id=existing_doc_id,
            owner_id=owner_id,
            original_filename="first.pdf",
            mime_type="application/pdf",
            file_size_bytes=len(pdf_content),
            storage_key=f"{owner_id}/{existing_doc_id}/first.pdf",
            file_hash_sha256="abc123...",
            status="ready",
        )
        
        db = AsyncMock()
        db.execute = AsyncMock(return_value=AsyncMock(scalar_one_or_none=AsyncMock(return_value=existing_doc)))
        
        file = UploadFile(filename="duplicate.pdf")
        file.read = AsyncMock(return_value=pdf_content)
        
        doc = await create_document(
            owner_id=owner_id,
            file=file,
            db=db,
        )
        
        # Should return existing document, not create new
        assert doc.id == existing_doc_id
        assert doc.original_filename == "first.pdf"
        db.add.assert_not_called()

    async def test_create_document_allows_same_hash_different_owner(self):
        # Different users can upload the same file (architecture.md §7.3: per-user dedup)
        pdf_content = b"%PDF-1.4\nShared content"
        file = UploadFile(filename="shared.pdf")
        file.read = AsyncMock(return_value=pdf_content)
        
        owner_id = uuid.uuid4()
        db = AsyncMock()
        # Dedup check: no existing document for *this* owner
        db.execute = AsyncMock(return_value=AsyncMock(scalar_one_or_none=AsyncMock(return_value=None)))
        
        with patch("app.services.ingestion.upload_to_s3", new_callable=AsyncMock), \
             patch("app.services.ingestion.record_audit_event", new_callable=AsyncMock):
            
            doc = await create_document(
                owner_id=owner_id,
                file=file,
                db=db,
            )
        
        assert doc.owner_id == owner_id
        db.add.assert_called_once()

    async def test_create_document_strips_path_from_filename(self):
        # Security: prevent directory traversal via filename
        pdf_content = b"%PDF-1.4\n..."
        file = UploadFile(filename="../../../etc/passwd.pdf")
        file.read = AsyncMock(return_value=pdf_content)
        
        owner_id = uuid.uuid4()
        db = AsyncMock()
        db.execute = AsyncMock(return_value=AsyncMock(scalar_one_or_none=AsyncMock(return_value=None)))
        
        with patch("app.services.ingestion.upload_to_s3", new_callable=AsyncMock), \
             patch("app.services.ingestion.record_audit_event", new_callable=AsyncMock):
            
            doc = await create_document(
                owner_id=owner_id,
                file=file,
                db=db,
            )
        
        # Path components should be stripped
        assert doc.original_filename == "passwd.pdf"
        assert "../" not in doc.storage_key

    async def test_create_document_writes_audit_log(self):
        pdf_content = b"%PDF-1.4\n..."
        file = UploadFile(filename="test.pdf")
        file.read = AsyncMock(return_value=pdf_content)
        
        owner_id = uuid.uuid4()
        db = AsyncMock()
        db.execute = AsyncMock(return_value=AsyncMock(scalar_one_or_none=AsyncMock(return_value=None)))
        
        with patch("app.services.ingestion.upload_to_s3", new_callable=AsyncMock), \
             patch("app.services.ingestion.record_audit_event", new_callable=AsyncMock) as mock_audit:
            
            doc = await create_document(
                owner_id=owner_id,
                file=file,
                db=db,
                ip_address="192.0.2.1",
            )
        
        # Verify audit event was recorded
        mock_audit.assert_awaited_once()
        call_kwargs = mock_audit.call_args.kwargs
        assert call_kwargs["actor_id"] == owner_id
        assert call_kwargs["action"] == "document.upload"
        assert call_kwargs["resource_id"] == doc.id
        assert call_kwargs["ip_address"] == "192.0.2.1"
