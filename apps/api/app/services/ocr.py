"""
OCR Service — LegalLens Phase 2
Implements: architecture.md §3 step 2 (Tesseract OCR fallback for scanned pages).
code-standards.md error handling: below-threshold confidence → flagged with caveat.
"""

from __future__ import annotations

import io

import structlog
import fitz  # PyMuPDF for rendering
import pytesseract
from PIL import Image

log = structlog.get_logger(__name__)

# Confidence threshold: <60 = low quality, flagged with caveat
LOW_CONFIDENCE_THRESHOLD = 60


def ocr_pdf_page(pdf_bytes: bytes, page_number: int) -> str:
    """
    OCR a single PDF page using Tesseract.
    Steps:
      1. Render page to image (PyMuPDF pixmap)
      2. Run Tesseract OCR
      3. Calculate confidence score
      4. Return text (with low-confidence warning logged if needed)
    
    Args:
        pdf_bytes: Raw PDF file bytes
        page_number: 1-indexed page number to OCR
    
    Returns:
        Extracted text string
    
    Raises:
        ValueError: If page rendering or OCR fails
    """
    try:
        # Render PDF page to PNG image
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            page = doc[page_number - 1]  # Convert to 0-indexed
            pixmap = page.get_pixmap(dpi=300)  # High DPI for better OCR
            image_bytes = pixmap.tobytes("png")
        
        # OCR the rendered image
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(
            image,
            lang="eng",
            config="--psm 1",  # Automatic page segmentation with OSD
        )
        
        # Calculate confidence
        confidence = _calculate_confidence(image_bytes)
        
        if confidence < LOW_CONFIDENCE_THRESHOLD:
            log.warning(
                "ocr.low_confidence",
                page_number=page_number,
                confidence=confidence,
            )
        
        log.info(
            "ocr.page_processed",
            page_number=page_number,
            confidence=confidence,
            char_count=len(text),
        )
        return text
        
    except Exception as exc:
        log.error("ocr.failed", page_number=page_number, error=str(exc))
        raise ValueError(f"Failed to OCR PDF page {page_number}: {exc}") from exc


def ocr_image_bytes(image_bytes: bytes) -> str:
    """
    OCR raw image bytes (PNG/JPEG).
    Used for standalone image OCR (not currently in Phase 2 scope,
    but available for future image-based document support).
    
    Raises:
        ValueError: If OCR fails
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(
            image,
            lang="eng",
            config="--psm 1",
        )
        log.info("ocr.image_processed", char_count=len(text))
        return text
    except Exception as exc:
        log.error("ocr.image_failed", error=str(exc))
        raise ValueError(f"OCR failed: {exc}") from exc


def _calculate_confidence(image_bytes: bytes) -> float:
    """
    Calculate average OCR confidence score.
    Tesseract outputs per-word confidence in image_to_data().
    Returns average confidence as a percentage (0-100).
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        
        # Extract confidence scores (filter out -1 which means no text detected)
        confidences = [
            int(conf) for conf in data.get("conf", [])
            if conf != -1 and str(conf).strip() and str(conf).strip() != "-1"
        ]
        
        if not confidences:
            return 0.0
        
        avg_confidence = sum(confidences) / len(confidences)
        return round(avg_confidence, 2)
        
    except Exception as exc:
        log.warning("ocr.confidence_calculation_failed", error=str(exc))
        return 0.0
