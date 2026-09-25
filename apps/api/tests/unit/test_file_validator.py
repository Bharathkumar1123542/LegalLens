"""
Unit tests — File validator
Tests: MIME detection, size validation, dangerous patterns, structure validation
Covers: app/core/file_validator.py (Phase 8 security)
"""

import pytest
from fastapi import HTTPException

from app.core.file_validator import (
    validate_file_size,
    detect_mime_type_strict,
    check_dangerous_patterns,
    validate_pdf_structure,
    validate_docx_structure,
    get_safe_filename,
    FileValidationError,
    ALLOWED_MIME_TYPES,
)


class TestValidateFileSize:
    """Test file size validation."""

    def test_valid_pdf_size(self):
        """PDF within size limit passes."""
        file_bytes = b"test" * 1000  # Small file
        validate_file_size(file_bytes, "application/pdf")
        # No exception = pass
    
    def test_pdf_too_large(self):
        """PDF exceeding limit raises error."""
        file_bytes = b"x" * (51 * 1024 * 1024)  # 51 MB
        
        with pytest.raises(FileValidationError, match="PDF too large"):
            validate_file_size(file_bytes, "application/pdf")
    
    def test_docx_too_large(self):
        """DOCX exceeding limit raises error."""
        file_bytes = b"x" * (26 * 1024 * 1024)  # 26 MB
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        
        with pytest.raises(FileValidationError, match="DOCX too large"):
            validate_file_size(file_bytes, mime)
    
    def test_text_too_large(self):
        """Text file exceeding limit raises error."""
        file_bytes = b"x" * (11 * 1024 * 1024)  # 11 MB
        
        with pytest.raises(FileValidationError, match="Text file too large"):
            validate_file_size(file_bytes, "text/plain")
    
    def test_global_limit_exceeded(self):
        """File exceeding global limit raises error."""
        file_bytes = b"x" * (101 * 1024 * 1024)  # >100 MB (global limit)
        
        with pytest.raises(FileValidationError, match="exceeds global limit"):
            validate_file_size(file_bytes, "application/pdf")


class TestDetectMimeTypeStrict:
    """Test strict MIME type detection."""

    def test_detect_pdf(self):
        """PDF magic bytes correctly detected."""
        pdf_bytes = b"%PDF-1.4\n%test content"
        mime = detect_mime_type_strict(pdf_bytes, "document.pdf")
        assert mime == "application/pdf"
    
    def test_detect_docx(self):
        """DOCX (ZIP with word/) correctly detected."""
        # Simplified DOCX signature (real DOCX is more complex)
        docx_bytes = b"PK\x03\x04" + b"\x00" * 100 + b"word/document.xml"
        mime = detect_mime_type_strict(docx_bytes, "document.docx")
        assert mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    
    def test_mime_type_mismatch(self):
        """File with wrong extension raises error."""
        pdf_bytes = b"%PDF-1.4\ntest"
        
        with pytest.raises(FileValidationError, match="type mismatch"):
            detect_mime_type_strict(pdf_bytes, "document.docx")  # PDF with .docx extension
    
    def test_unsupported_mime_type(self):
        """Unsupported file type raises error."""
        jpeg_bytes = b"\xff\xd8\xff\xe0"  # JPEG magic bytes
        
        with pytest.raises(FileValidationError, match="Unsupported file type"):
            detect_mime_type_strict(jpeg_bytes, "image.jpg")
    
    def test_empty_file(self):
        """Empty file raises error."""
        with pytest.raises(FileValidationError):
            detect_mime_type_strict(b"", "empty.pdf")


class TestCheckDangerousPatterns:
    """Test dangerous pattern detection."""

    def test_javascript_detected(self):
        """JavaScript in file raises error."""
        file_bytes = b"Some content <script>alert('xss')</script>"
        
        with pytest.raises(FileValidationError, match="suspicious content"):
            check_dangerous_patterns(file_bytes, "test.txt")
    
    def test_php_code_detected(self):
        """PHP code in file raises error."""
        file_bytes = b"<?php echo 'malicious'; ?>"
        
        with pytest.raises(FileValidationError, match="suspicious content"):
            check_dangerous_patterns(file_bytes, "test.txt")
    
    def test_shell_script_detected(self):
        """Shell script detected."""
        file_bytes = b"#!/bin/bash\nrm -rf /"
        
        with pytest.raises(FileValidationError, match="suspicious content"):
            check_dangerous_patterns(file_bytes, "test.txt")
    
    def test_executable_detected(self):
        """PE executable detected."""
        file_bytes = b"MZ\x90\x00"  # PE header
        
        with pytest.raises(FileValidationError, match="suspicious content"):
            check_dangerous_patterns(file_bytes, "test.exe")
    
    def test_null_bytes_in_text(self):
        """Null bytes in text file detected."""
        file_bytes = b"Text with\x00null byte"
        
        with pytest.raises(FileValidationError, match="binary content"):
            check_dangerous_patterns(file_bytes, "document.txt")
    
    def test_clean_file_passes(self):
        """Clean file passes check."""
        file_bytes = b"This is a normal text file with no dangerous content."
        check_dangerous_patterns(file_bytes, "clean.txt")
        # No exception = pass


class TestValidatePDFStructure:
    """Test PDF structure validation."""

    def test_valid_pdf_structure(self):
        """Valid PDF structure passes."""
        pdf_bytes = b"%PDF-1.4\n%content here\n%%EOF"
        validate_pdf_structure(pdf_bytes)
        # No exception = pass
    
    def test_missing_pdf_header(self):
        """PDF without header raises error."""
        pdf_bytes = b"Not a PDF file"
        
        with pytest.raises(FileValidationError, match="missing PDF header"):
            validate_pdf_structure(pdf_bytes)
    
    def test_pdf_without_eof(self):
        """PDF without EOF marker still passes (warning only)."""
        pdf_bytes = b"%PDF-1.4\ncontent but no EOF"
        validate_pdf_structure(pdf_bytes)
        # Should log warning but not raise


class TestValidateDOCXStructure:
    """Test DOCX structure validation."""

    def test_valid_docx_structure(self):
        """Valid DOCX structure passes."""
        docx_bytes = b"PK\x03\x04" + b"\x00" * 50 + b"word/document.xml"
        validate_docx_structure(docx_bytes)
        # No exception = pass
    
    def test_missing_zip_signature(self):
        """DOCX without ZIP signature raises error."""
        docx_bytes = b"Not a ZIP file"
        
        with pytest.raises(FileValidationError, match="missing ZIP signature"):
            validate_docx_structure(docx_bytes)
    
    def test_zip_without_word_structure(self):
        """ZIP file without Word structure raises error."""
        docx_bytes = b"PK\x03\x04" + b"\x00" * 100  # ZIP but no word/
        
        with pytest.raises(FileValidationError, match="missing Word document structure"):
            validate_docx_structure(docx_bytes)


class TestGetSafeFilename:
    """Test filename sanitization."""

    def test_normal_filename(self):
        """Normal filename unchanged."""
        safe = get_safe_filename("document.pdf")
        assert safe == "document.pdf"
    
    def test_path_traversal_removed(self):
        """Path traversal attempts removed."""
        safe = get_safe_filename("../../etc/passwd")
        assert ".." not in safe
        assert "/" not in safe
        assert safe == "passwd"
    
    def test_dangerous_characters_removed(self):
        """Dangerous characters replaced."""
        safe = get_safe_filename("doc<script>.pdf")
        assert "<" not in safe
        assert ">" not in safe
        assert safe == "doc_script_.pdf"
    
    def test_long_filename_truncated(self):
        """Very long filename truncated."""
        long_name = "a" * 250 + ".pdf"
        safe = get_safe_filename(long_name)
        assert len(safe) <= 200
        assert safe.endswith(".pdf")
    
    def test_empty_filename_replaced(self):
        """Empty filename gets default."""
        safe = get_safe_filename("")
        assert safe == "document.pdf"
    
    def test_dot_only_replaced(self):
        """Dot-only filename replaced."""
        safe = get_safe_filename(".")
        assert safe == "document.pdf"
    
    def test_spaces_preserved(self):
        """Spaces in filename preserved."""
        safe = get_safe_filename("my document.pdf")
        assert safe == "my document.pdf"


class TestAllowedMimeTypes:
    """Test allowed MIME types configuration."""

    def test_pdf_allowed(self):
        """PDF MIME type in allowed list."""
        assert "application/pdf" in ALLOWED_MIME_TYPES
    
    def test_docx_allowed(self):
        """DOCX MIME type in allowed list."""
        assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in ALLOWED_MIME_TYPES
    
    def test_text_allowed(self):
        """Text MIME type in allowed list."""
        assert "text/plain" in ALLOWED_MIME_TYPES
    
    def test_only_three_types(self):
        """Only three MIME types allowed."""
        assert len(ALLOWED_MIME_TYPES) == 3
    
    def test_no_executables_allowed(self):
        """Executable types not allowed."""
        dangerous = [
            "application/x-msdownload",  # .exe
            "application/x-sh",           # shell script
            "text/x-python",              # Python script
            "application/javascript",     # JavaScript
        ]
        for mime in dangerous:
            assert mime not in ALLOWED_MIME_TYPES
