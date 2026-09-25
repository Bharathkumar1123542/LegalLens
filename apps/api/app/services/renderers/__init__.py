"""
Renderers — LegalLens Export Format Conversion

Converts Markdown-formatted export content to various output formats:
- PDF (via reportlab)
- DOCX (via python-docx)
- Markdown (pass-through)

All renderers accept Markdown input and return bytes for storage.
"""

from __future__ import annotations

__all__ = ["render_to_pdf", "render_to_docx", "render_to_markdown"]


def render_to_markdown(markdown_content: str) -> bytes:
    """
    Render Markdown as UTF-8 bytes (pass-through).
    
    Args:
        markdown_content: Markdown-formatted string
    
    Returns:
        UTF-8 encoded bytes
    """
    return markdown_content.encode('utf-8')


def render_to_pdf(markdown_content: str) -> bytes:
    """
    Render Markdown to PDF format.
    
    Args:
        markdown_content: Markdown-formatted string
    
    Returns:
        PDF file as bytes
    """
    from app.services.renderers.pdf_renderer import markdown_to_pdf
    return markdown_to_pdf(markdown_content)


def render_to_docx(markdown_content: str) -> bytes:
    """
    Render Markdown to DOCX format.
    
    Args:
        markdown_content: Markdown-formatted string
    
    Returns:
        DOCX file as bytes
    """
    from app.services.renderers.docx_renderer import markdown_to_docx
    return markdown_to_docx(markdown_content)
