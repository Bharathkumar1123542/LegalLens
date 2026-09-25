"""
Unit tests — text extraction service
Tests: PDF extraction (PyMuPDF), DOCX extraction (python-docx), plain text passthrough.
Covers: architecture.md §3 step 2, code-standards.md error handling (corrupted files).
"""

import io
from unittest.mock import MagicMock, patch, mock_open

import pytest

from app.services.text_extraction import (
    extract_text_from_pdf,
    extract_text_from_docx,
    extract_text_from_plain,
    detect_scanned_pdf_pages,
)


class TestPDFExtraction:
    """Test PDF text extraction with PyMuPDF."""

    @patch("app.services.text_extraction.fitz")
    def test_extract_text_from_pdf_with_text_layer(self, mock_fitz):
        # Mock a 2-page PDF with text
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 2
        mock_page1 = MagicMock()
        mock_page1.get_text.return_value = "Page 1 content with text."
        mock_page2 = MagicMock()
        mock_page2.get_text.return_value = "Page 2 content here."
        mock_doc.__getitem__.side_effect = [mock_page1, mock_page2]
        mock_fitz.open.return_value.__enter__.return_value = mock_doc
        
        pdf_bytes = b"%PDF-1.4 fake content"
        pages = extract_text_from_pdf(pdf_bytes)
        
        assert len(pages) == 2
        assert pages[0]["page_number"] == 1
        assert pages[0]["text"] == "Page 1 content with text."
        assert pages[0]["needs_ocr"] is False
        assert pages[1]["page_number"] == 2
        assert pages[1]["text"] == "Page 2 content here."

    @patch("app.services.text_extraction.fitz")
    def test_extract_text_from_pdf_detects_scanned_pages(self, mock_fitz):
        # Page with minimal text (likely scanned)
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 1
        mock_page = MagicMock()
        mock_page.get_text.return_value = "  \n  "  # Whitespace only
        mock_doc.__getitem__.return_value = mock_page
        mock_fitz.open.return_value.__enter__.return_value = mock_doc
        
        pdf_bytes = b"%PDF-1.4"
        pages = extract_text_from_pdf(pdf_bytes)
        
        assert len(pages) == 1
        assert pages[0]["needs_ocr"] is True
        assert pages[0]["text"].strip() == ""

    @patch("app.services.text_extraction.fitz")
    def test_extract_text_from_pdf_handles_corrupted_file(self, mock_fitz):
        # PyMuPDF raises on corrupted PDF
        mock_fitz.open.side_effect = Exception("PDF structure error")
        
        with pytest.raises(ValueError, match="Failed to parse PDF"):
            extract_text_from_pdf(b"corrupted")


class TestDOCXExtraction:
    """Test DOCX text extraction with python-docx."""

    @patch("app.services.text_extraction.Document")
    def test_extract_text_from_docx_success(self, mock_doc_class):
        # Mock DOCX with 3 paragraphs
        mock_doc = MagicMock()
        mock_para1 = MagicMock()
        mock_para1.text = "First paragraph."
        mock_para2 = MagicMock()
        mock_para2.text = "Second paragraph."
        mock_para3 = MagicMock()
        mock_para3.text = ""  # Empty paragraph (should be filtered)
        mock_doc.paragraphs = [mock_para1, mock_para2, mock_para3]
        mock_doc_class.return_value = mock_doc
        
        docx_bytes = b"PK\x03\x04fake docx"
        text = extract_text_from_docx(docx_bytes)
        
        assert text == "First paragraph.\n\nSecond paragraph."

    @patch("app.services.text_extraction.Document")
    def test_extract_text_from_docx_handles_corrupted_file(self, mock_doc_class):
        mock_doc_class.side_effect = Exception("Not a valid DOCX")
        
        with pytest.raises(ValueError, match="Failed to parse DOCX"):
            extract_text_from_docx(b"corrupted")


class TestPlainTextExtraction:
    """Test plain text passthrough."""

    def test_extract_text_from_plain_utf8(self):
        text_bytes = "Hello, this is plain text.\nSecond line.".encode("utf-8")
        text = extract_text_from_plain(text_bytes)
        
        assert text == "Hello, this is plain text.\nSecond line."

    def test_extract_text_from_plain_handles_decode_errors(self):
        # Invalid UTF-8 sequence
        invalid_bytes = b"\xff\xfeInvalid UTF-8"
        
        with pytest.raises(ValueError, match="Failed to decode"):
            extract_text_from_plain(invalid_bytes)


class TestScanDetection:
    """Test scanned PDF page detection heuristic."""

    def test_detect_scanned_pdf_pages_with_no_text(self):
        pages = [
            {"page_number": 1, "text": "   ", "needs_ocr": False},
            {"page_number": 2, "text": "", "needs_ocr": False},
        ]
        scanned_pages = detect_scanned_pdf_pages(pages)
        
        assert scanned_pages == [1, 2]

    def test_detect_scanned_pdf_pages_with_mixed_content(self):
        pages = [
            {"page_number": 1, "text": "Good text layer here.", "needs_ocr": False},
            {"page_number": 2, "text": "  \n ", "needs_ocr": False},  # Scanned
            {"page_number": 3, "text": "More readable text.", "needs_ocr": False},
        ]
        scanned_pages = detect_scanned_pdf_pages(pages)
        
        assert scanned_pages == [2]

    def test_detect_scanned_pdf_pages_all_readable(self):
        pages = [
            {"page_number": 1, "text": "Page 1 content", "needs_ocr": False},
            {"page_number": 2, "text": "Page 2 content", "needs_ocr": False},
        ]
        scanned_pages = detect_scanned_pdf_pages(pages)
        
        assert scanned_pages == []
