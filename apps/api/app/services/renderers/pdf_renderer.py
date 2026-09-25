"""
PDF Renderer — Convert Markdown to PDF using reportlab

Supports:
- Headings (# ## ###)
- Bold (**text**)
- Italic (*text*)
- Lists (- item)
- Paragraphs
- Page numbers
- Headers/footers
"""

from __future__ import annotations

import io
import re
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    ListFlowable,
    ListItem,
)
from reportlab.lib.colors import HexColor


def markdown_to_pdf(markdown_content: str) -> bytes:
    """
    Convert Markdown content to PDF.
    
    Args:
        markdown_content: Markdown-formatted string
    
    Returns:
        PDF file as bytes
    """
    buffer = io.BytesIO()
    
    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
    )
    
    # Build styles
    styles = _build_styles()
    
    # Parse Markdown and build story
    story = _parse_markdown_to_story(markdown_content, styles)
    
    # Add header/footer with page numbers
    doc.build(story, onFirstPage=_add_page_number, onLaterPages=_add_page_number)
    
    # Get PDF bytes
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes


def _build_styles() -> dict:
    """Build reportlab styles for various elements."""
    base_styles = getSampleStyleSheet()
    
    styles = {
        'Normal': base_styles['Normal'],
        'Heading1': ParagraphStyle(
            'Heading1',
            parent=base_styles['Heading1'],
            fontSize=18,
            textColor=HexColor('#1a1a1a'),
            spaceAfter=12,
            spaceBefore=12,
            fontName='Helvetica-Bold',
        ),
        'Heading2': ParagraphStyle(
            'Heading2',
            parent=base_styles['Heading2'],
            fontSize=14,
            textColor=HexColor('#333333'),
            spaceAfter=10,
            spaceBefore=10,
            fontName='Helvetica-Bold',
        ),
        'Heading3': ParagraphStyle(
            'Heading3',
            parent=base_styles['Heading3'],
            fontSize=12,
            textColor=HexColor('#555555'),
            spaceAfter=8,
            spaceBefore=8,
            fontName='Helvetica-Bold',
        ),
        'Body': ParagraphStyle(
            'Body',
            parent=base_styles['Normal'],
            fontSize=10,
            leading=14,
            spaceAfter=8,
            alignment=TA_LEFT,
        ),
        'ListItem': ParagraphStyle(
            'ListItem',
            parent=base_styles['Normal'],
            fontSize=10,
            leading=14,
            leftIndent=20,
        ),
    }
    
    return styles


def _parse_markdown_to_story(markdown_content: str, styles: dict) -> list:
    """
    Parse Markdown and convert to reportlab story elements.
    
    Supports:
    - # ## ### headings
    - **bold** and *italic*
    - - list items
    - Paragraphs
    """
    story = []
    lines = markdown_content.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines
        if not line:
            i += 1
            continue
        
        # Heading 1
        if line.startswith('# '):
            text = line[2:].strip()
            text = _convert_markdown_formatting(text)
            story.append(Paragraph(text, styles['Heading1']))
            story.append(Spacer(1, 0.2 * inch))
        
        # Heading 2
        elif line.startswith('## '):
            text = line[3:].strip()
            text = _convert_markdown_formatting(text)
            story.append(Paragraph(text, styles['Heading2']))
            story.append(Spacer(1, 0.15 * inch))
        
        # Heading 3
        elif line.startswith('### '):
            text = line[4:].strip()
            text = _convert_markdown_formatting(text)
            story.append(Paragraph(text, styles['Heading3']))
            story.append(Spacer(1, 0.1 * inch))
        
        # List item
        elif line.startswith('- ') or line.startswith('* '):
            # Collect consecutive list items
            list_items = []
            while i < len(lines) and (lines[i].strip().startswith('- ') or lines[i].strip().startswith('* ')):
                item_text = lines[i].strip()[2:].strip()
                item_text = _convert_markdown_formatting(item_text)
                list_items.append(ListItem(Paragraph(item_text, styles['ListItem'])))
                i += 1
            
            story.append(ListFlowable(list_items, bulletType='bullet'))
            story.append(Spacer(1, 0.1 * inch))
            continue  # i already incremented
        
        # Horizontal rule
        elif line.startswith('---') or line.startswith('***'):
            story.append(Spacer(1, 0.1 * inch))
            story.append(PageBreak())
        
        # Regular paragraph
        else:
            text = _convert_markdown_formatting(line)
            story.append(Paragraph(text, styles['Body']))
            story.append(Spacer(1, 0.1 * inch))
        
        i += 1
    
    return story


def _convert_markdown_formatting(text: str) -> str:
    """
    Convert Markdown formatting to reportlab HTML tags.
    
    Converts:
    - **bold** → <b>bold</b>
    - *italic* → <i>italic</i>
    """
    # Bold: **text** → <b>text</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    
    # Italic: *text* → <i>text</i>
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    
    # Escape XML special characters (except our tags)
    # text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    # Actually, reportlab Paragraph handles this, so we can leave as-is
    
    return text


def _add_page_number(canvas, doc):
    """
    Add page number footer to each page.
    
    Called by reportlab for each page.
    """
    page_num = canvas.getPageNumber()
    text = f"Page {page_num}"
    
    canvas.saveState()
    canvas.setFont('Helvetica', 9)
    canvas.setFillColor(HexColor('#666666'))
    
    # Center footer
    canvas.drawCentredString(
        letter[0] / 2.0,
        0.5 * inch,
        text,
    )
    
    # Add generation timestamp in top-right
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    canvas.drawRightString(
        letter[0] - inch,
        letter[1] - 0.5 * inch,
        f"Generated: {timestamp}",
    )
    
    canvas.restoreState()
