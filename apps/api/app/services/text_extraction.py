"""
Text Extraction Service — LegalLens Phase 2
Implements: architecture.md §3 step 2 (text extraction, OCR detection).
Supports: PDF (PyMuPDF), DOCX (python-docx), plain text.
"""

from __future__ import annotations

import io
from typing import TypedDict

import structlog
import fitz  # PyMuPDF
from docx import Document

log = structlog.get_logger(__name__)


class PageText(TypedDict):
    """Single page extraction result."""
    page_number: int
    text: str
    needs_ocr: bool


def extract_text_from_pdf(pdf_bytes: bytes) -> list[PageText]:
    """
    Extract text from PDF using PyMuPDF.
    Returns a list of pages with text and OCR-need flag.
    Raises ValueError on corrupted/unparseable PDF.
    """
    try:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            pages: list[PageText] = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                # Heuristic: if page has <10 chars of non-whitespace, likely scanned
                needs_ocr = len(text.strip()) < 10
                pages.append({
                    "page_number": page_num + 1,  # 1-indexed for user display
                    "text": text,
                    "needs_ocr": needs_ocr,
                })
            log.info("pdf.text_extracted", page_count=len(pages))
            return pages
    except Exception as exc:
        log.error("pdf.parse_failed", error=str(exc))
        raise ValueError(f"Failed to parse PDF: {exc}") from exc


def extract_text_from_docx(docx_bytes: bytes) -> str:
    """
    Extract text from DOCX using python-docx.
    Returns concatenated paragraph text (double newline between paragraphs).
    Raises ValueError on corrupted/unparseable DOCX.
    """
    try:
        doc = Document(io.BytesIO(docx_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n\n".join(paragraphs)
        log.info("docx.text_extracted", paragraph_count=len(paragraphs))
        return text
    except Exception as exc:
        log.error("docx.parse_failed", error=str(exc))
        raise ValueError(f"Failed to parse DOCX: {exc}") from exc


def extract_text_from_plain(text_bytes: bytes) -> str:
    """
    Decode plain text file.
    Raises ValueError on decode failure.
    """
    try:
        text = text_bytes.decode("utf-8")
        log.info("plaintext.decoded", byte_count=len(text_bytes))
        return text
    except UnicodeDecodeError as exc:
        log.error("plaintext.decode_failed", error=str(exc))
        raise ValueError(f"Failed to decode plain text as UTF-8: {exc}") from exc


def detect_scanned_pdf_pages(pages: list[PageText]) -> list[int]:
    """
    Return list of page numbers (1-indexed) that need OCR.
    Heuristic: page with <10 non-whitespace characters.
    """
    scanned = [p["page_number"] for p in pages if len(p["text"].strip()) < 10]
    if scanned:
        log.info("pdf.scanned_pages_detected", page_numbers=scanned)
    return scanned
