"""
Unit tests — OCR service
Tests: Tesseract OCR invocation, confidence threshold handling, image preprocessing.
Covers: architecture.md §3 step 2 OCR fallback, code-standards.md error handling.
"""

import io
from unittest.mock import MagicMock, patch, Mock

import pytest

from app.services.ocr import ocr_pdf_page, ocr_image_bytes


class TestOCRPDFPage:
    """Test OCR extraction from PDF page."""

    @patch("app.services.ocr.fitz")
    @patch("app.services.ocr.pytesseract")
    @patch("app.services.ocr.Image")
    def test_ocr_pdf_page_success(self, mock_pil, mock_tesseract, mock_fitz):
        # Mock PDF page rendering
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_pixmap = MagicMock()
        mock_pixmap.tobytes.return_value = b"fake_png_bytes"
        mock_page.get_pixmap.return_value = mock_pixmap
        mock_doc.__getitem__.return_value = mock_page
        mock_fitz.open.return_value.__enter__.return_value = mock_doc
        
        # Mock PIL Image
        mock_image = MagicMock()
        mock_pil.open.return_value = mock_image
        
        # Mock Tesseract OCR
        mock_tesseract.image_to_string.return_value = "OCR extracted text from scanned page."
        mock_tesseract.image_to_data.return_value = "conf\n95"  # High confidence
        
        pdf_bytes = b"%PDF-1.4"
        page_number = 1
        text = ocr_pdf_page(pdf_bytes, page_number)
        
        assert text == "OCR extracted text from scanned page."
        mock_page.get_pixmap.assert_called_once()
        mock_tesseract.image_to_string.assert_called_once()

    @patch("app.services.ocr.fitz")
    @patch("app.services.ocr.pytesseract")
    @patch("app.services.ocr.Image")
    def test_ocr_pdf_page_low_confidence(self, mock_pil, mock_tesseract, mock_fitz):
        # Mock low-confidence OCR result
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_pixmap = MagicMock()
        mock_pixmap.tobytes.return_value = b"fake_png"
        mock_page.get_pixmap.return_value = mock_pixmap
        mock_doc.__getitem__.return_value = mock_page
        mock_fitz.open.return_value.__enter__.return_value = mock_doc
        
        mock_image = MagicMock()
        mock_pil.open.return_value = mock_image
        
        mock_tesseract.image_to_string.return_value = "Low quality text"
        # Low confidence scores
        mock_tesseract.image_to_data.return_value = "conf\n30\n25\n40"
        
        text = ocr_pdf_page(pdf_bytes=b"%PDF", page_number=1)
        
        # Should still return text but log warning
        assert text == "Low quality text"

    @patch("app.services.ocr.fitz")
    def test_ocr_pdf_page_handles_render_failure(self, mock_fitz):
        # Page rendering fails
        mock_fitz.open.side_effect = Exception("Failed to render page")
        
        with pytest.raises(ValueError, match="Failed to OCR PDF page"):
            ocr_pdf_page(b"%PDF", 1)


class TestOCRImageBytes:
    """Test OCR extraction from raw image bytes."""

    @patch("app.services.ocr.pytesseract")
    @patch("app.services.ocr.Image")
    def test_ocr_image_bytes_success(self, mock_pil, mock_tesseract):
        mock_image = MagicMock()
        mock_pil.open.return_value = mock_image
        
        mock_tesseract.image_to_string.return_value = "Text from image."
        
        image_bytes = b"fake_png_data"
        text = ocr_image_bytes(image_bytes)
        
        assert text == "Text from image."
        mock_pil.open.assert_called_once()
        mock_tesseract.image_to_string.assert_called_once_with(
            mock_image,
            lang="eng",
            config="--psm 1",
        )

    @patch("app.services.ocr.pytesseract")
    @patch("app.services.ocr.Image")
    def test_ocr_image_bytes_handles_tesseract_failure(self, mock_pil, mock_tesseract):
        mock_image = MagicMock()
        mock_pil.open.return_value = mock_image
        
        # Tesseract raises on unrecognizable image
        mock_tesseract.image_to_string.side_effect = Exception("Tesseract error")
        
        with pytest.raises(ValueError, match="OCR failed"):
            ocr_image_bytes(b"corrupted_image")


class TestConfidenceCalculation:
    """Test OCR confidence scoring."""

    @patch("app.services.ocr.pytesseract")
    @patch("app.services.ocr.Image")
    def test_calculate_average_confidence(self, mock_pil, mock_tesseract):
        mock_image = MagicMock()
        mock_pil.open.return_value = mock_image
        
        # Mock confidence data with mixed scores
        mock_tesseract.image_to_data.return_value = (
            "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
            "5\t1\t1\t1\t1\t1\t10\t20\t50\t15\t95\tWord1\n"
            "5\t1\t1\t1\t1\t2\t70\t20\t60\t15\t88\tWord2\n"
            "5\t1\t1\t1\t2\t1\t10\t40\t55\t15\t92\tWord3\n"
        )
        mock_tesseract.image_to_string.return_value = "Word1 Word2 Word3"
        
        from app.services.ocr import _calculate_confidence
        confidence = _calculate_confidence(b"image")
        
        # Average of 95, 88, 92 = 91.67
        assert 90 <= confidence <= 93
