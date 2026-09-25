"""
Unit tests — services/ingestion.py (magic-byte detection + validation)
code-standards.md: "Security-critical paths (auth, file validation, ownership checks,
PII disclosure flow): 100% coverage, non-waivable."

Tests the magic-byte MIME detection and the validation rules defined in
architecture.md §7.3 and code-standards.md §Security — WITHOUT touching S3 or DB.
S3 and DB calls are patched out; the function under test is _detect_mime_type
and the validation logic in create_document().
"""

from __future__ import annotations

import hashlib
import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, UploadFile

from app.services.ingestion import (
    ALLOWED_MIME_TYPES,
    _detect_mime_type,
    create_document,
)


# ── Magic-byte detection ──────────────────────────────────────────────────────

class TestDetectMimeType:
    """Tests _detect_mime_type() against real file headers."""

    def test_pdf_header_detected(self):
        assert _detect_mime_type(b"%PDF-1.4 ...") == "application/pdf"

    def test_docx_header_detected(self):
        # DOCX is a ZIP file starting with PK\x03\x04
        assert _detect_mime_type(b"\x50\x4B\x03\x04" + b"\x00" * 12) == (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    def test_plain_text_utf8_detected(self):
        assert _detect_mime_type(b"This is plain English text.") == "text/plain"

    def test_binary_with_null_bytes_rejected(self):
        assert _detect_mime_type(b"\x00\x01\x02\x03binary garbage") is None

    def test_non_utf8_bytes_rejected(self):
        assert _detect_mime_type(b"\xff\xfe\x80\x81") is None

    def test_unknown_magic_non_text_rejected(self):
        # ELF binary header
        assert _detect_mime_type(b"\x7fELF\x02\x01\x01\x00") is None

    def test_jpeg_rejected(self):
        assert _detect_mime_type(b"\xff\xd8\xff\xe0JFIF") is None

    def test_empty_bytes_returns_text(self):
        # Empty header is technically valid UTF-8 — detected as text/plain
        result = _detect_mime_type(b"")
        assert result == "text/plain"

    def test_all_allowed_types_are_detectable(self):
        headers_and_expected = [
            (b"%PDF-1.4", "application/pdf"),
            (b"\x50\x4B\x03\x04" + b"\x00" * 12,
             "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            (b"Plain text content here", "text/plain"),
        ]
        for header, expected in headers_and_expected:
            assert _detect_mime_type(header) == expected


# ── create_document() validation ──────────────────────────────────────────────

OWNER_ID = uuid.uuid4()
PDF_HEADER = b"%PDF-1.4 fake pdf content for testing"


def _make_upload_file(content: bytes, filename: str = "test.pdf") -> UploadFile:
    """Build a minimal UploadFile from raw bytes."""
    file = UploadFile(filename=filename, file=io.BytesIO(content))
    return file


class TestCreateDocumentValidation:
    """Tests create_document() validation without hitting S3 or DB."""

    @pytest.mark.asyncio
    async def test_empty_file_raises_400(self):
        db = AsyncMock()
        upload = _make_upload_file(b"")
        with pytest.raises(HTTPException) as exc_info:
            await create_document(OWNER_ID, upload, db)
        assert exc_info.value.status_code == 400
        assert "empty" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_unsupported_type_raises_400(self):
        db = AsyncMock()
        # JPEG bytes
        jpeg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 100
        upload = _make_upload_file(jpeg_bytes, "photo.jpg")
        with pytest.raises(HTTPException) as exc_info:
            await create_document(OWNER_ID, upload, db)
        assert exc_info.value.status_code == 400
        assert "Unsupported file type" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_oversized_file_raises_413(self):
        """File > MAX_UPLOAD_SIZE_MB should be rejected with 413."""
        db = AsyncMock()
        # Build content large enough to exceed the limit
        huge_content = b"%PDF-1.4 " + b"x" * (21 * 1024 * 1024)  # 21 MB
        upload = _make_upload_file(huge_content, "big.pdf")
        with pytest.raises(HTTPException) as exc_info:
            await create_document(OWNER_ID, upload, db)
        assert exc_info.value.status_code == 413

    @pytest.mark.asyncio
    async def test_deduplication_returns_existing_document(self):
        """Same hash + same owner → return existing Document without re-uploading."""
        existing_doc = MagicMock()
        existing_doc.id = uuid.uuid4()

        db = AsyncMock()
        # Simulate the SELECT returning an existing document
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_doc
        db.execute = AsyncMock(return_value=mock_result)

        upload = _make_upload_file(PDF_HEADER, "contract.pdf")

        with patch("app.services.ingestion.upload_to_s3", new_callable=AsyncMock) as mock_s3:
            result = await create_document(OWNER_ID, upload, db)

        assert result is existing_doc
        # S3 upload must NOT be called for a duplicate
        mock_s3.assert_not_called()

    @pytest.mark.asyncio
    async def test_successful_upload_creates_document_row(self):
        """Happy path: valid PDF → Document created with status=uploaded."""
        db = AsyncMock()
        # First execute: dedup check returns None (no existing doc)
        # Second execute: audit log flush
        no_existing = MagicMock()
        no_existing.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=no_existing)
        db.flush = AsyncMock()
        db.add = MagicMock()

        upload = _make_upload_file(PDF_HEADER, "contract.pdf")

        with patch("app.services.ingestion.upload_to_s3", new_callable=AsyncMock):
            with patch("app.services.ingestion.record_audit_event", new_callable=AsyncMock):
                result = await create_document(OWNER_ID, upload, db)

        assert result.status == "uploaded"
        assert result.owner_id == OWNER_ID
        assert result.mime_type == "application/pdf"
        assert result.original_filename == "contract.pdf"
        assert len(result.file_hash_sha256) == 64  # SHA-256 hex

    @pytest.mark.asyncio
    async def test_storage_key_contains_owner_and_doc_id(self):
        """storage_key must include owner_id and doc_id for S3 path isolation."""
        db = AsyncMock()
        no_existing = MagicMock()
        no_existing.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=no_existing)
        db.flush = AsyncMock()
        db.add = MagicMock()

        upload = _make_upload_file(PDF_HEADER, "contract.pdf")

        captured_key = {}
        async def fake_s3(key, data, content_type):
            captured_key["key"] = key

        with patch("app.services.ingestion.upload_to_s3", side_effect=fake_s3):
            with patch("app.services.ingestion.record_audit_event", new_callable=AsyncMock):
                result = await create_document(OWNER_ID, upload, db)

        key = captured_key["key"]
        assert str(OWNER_ID) in key
        assert str(result.id) in key

    @pytest.mark.asyncio
    async def test_path_traversal_in_filename_stripped(self):
        """Filenames like ../../etc/passwd must be sanitised."""
        db = AsyncMock()
        no_existing = MagicMock()
        no_existing.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=no_existing)
        db.flush = AsyncMock()
        db.add = MagicMock()

        upload = _make_upload_file(PDF_HEADER, "../../etc/passwd")

        with patch("app.services.ingestion.upload_to_s3", new_callable=AsyncMock):
            with patch("app.services.ingestion.record_audit_event", new_callable=AsyncMock):
                result = await create_document(OWNER_ID, upload, db)

        # Must not contain path traversal sequences
        assert ".." not in result.original_filename
        assert "/" not in result.original_filename
        assert result.original_filename == "passwd"

    @pytest.mark.asyncio
    async def test_sha256_computed_correctly(self):
        """file_hash_sha256 must be the correct SHA-256 of the file bytes."""
        db = AsyncMock()
        no_existing = MagicMock()
        no_existing.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=no_existing)
        db.flush = AsyncMock()
        db.add = MagicMock()

        content = PDF_HEADER
        expected_hash = hashlib.sha256(content).hexdigest()
        upload = _make_upload_file(content, "doc.pdf")

        with patch("app.services.ingestion.upload_to_s3", new_callable=AsyncMock):
            with patch("app.services.ingestion.record_audit_event", new_callable=AsyncMock):
                result = await create_document(OWNER_ID, upload, db)

        assert result.file_hash_sha256 == expected_hash
