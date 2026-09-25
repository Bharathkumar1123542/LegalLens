"""
DOCX Renderer — Convert Markdown to DOCX using python-docx

Supports:
- Headings (# ## ###)
- Bold (**text**)
- Italic (*text*)
- Lists (- item)
- Paragraphs
- Tables (basic)
"""

from __future__ import annotations

import io
import re
from datetime import datetime

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT


def markdown_to_docx(markdown_content: str) -> bytes:
    """
    Convert Markdown content to DOCX.
    
    Args:
        markdown_content: Markdown-formatted string
    
    Returns:
        DOCX file as bytes
    """
    doc = Document()
    
    # Set document margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)
    
    # Add header with generation timestamp
    header = doc.sections[0].header
    header_para = header.paragraphs[0]
    header_para.text = f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    header_para.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
    header_run = header_para.runs[0]
    header_run.font.size = Pt(9)
    header_run.font.color.rgb = RGBColor(102, 102, 102)
    
    # Parse Markdown and add to document
    _parse_markdown_to_docx(markdown_content, doc)
    
    # Save to bytes
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    docx_bytes = buffer.getvalue()
    buffer.close()
    
    return docx_bytes


def _parse_markdown_to_docx(markdown_content: str, doc: Document) -> None:
    """
    Parse Markdown and add elements to DOCX document.
    
    Supports:
    - # ## ### headings
    - **bold** and *italic*
    - - list items
    - Paragraphs
    """
    lines = markdown_content.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines (but add spacing)
        if not line:
            i += 1
            continue
        
        # Heading 1
        if line.startswith('# '):
            text = line[2:].strip()
            para = doc.add_heading(level=1)
            _add_formatted_text(para, text)
        
        # Heading 2
        elif line.startswith('## '):
            text = line[3:].strip()
            para = doc.add_heading(level=2)
            _add_formatted_text(para, text)
        
        # Heading 3
        elif line.startswith('### '):
            text = line[4:].strip()
            para = doc.add_heading(level=3)
            _add_formatted_text(para, text)
        
        # List item
        elif line.startswith('- ') or line.startswith('* '):
            # Collect consecutive list items
            while i < len(lines) and (lines[i].strip().startswith('- ') or lines[i].strip().startswith('* ')):
                item_text = lines[i].strip()[2:].strip()
                para = doc.add_paragraph(style='List Bullet')
                _add_formatted_text(para, item_text)
                i += 1
            continue  # i already incremented
        
        # Numbered list item
        elif re.match(r'^\d+\.\s', line):
            # Collect consecutive numbered items
            while i < len(lines) and re.match(r'^\d+\.\s', lines[i].strip()):
                item_text = re.sub(r'^\d+\.\s', '', lines[i].strip())
                para = doc.add_paragraph(style='List Number')
                _add_formatted_text(para, item_text)
                i += 1
            continue  # i already incremented
        
        # Horizontal rule (page break)
        elif line.startswith('---') or line.startswith('***'):
            doc.add_page_break()
        
        # Regular paragraph
        else:
            para = doc.add_paragraph()
            _add_formatted_text(para, line)
        
        i += 1


def _add_formatted_text(paragraph, text: str) -> None:
    """
    Add text with Markdown formatting to a DOCX paragraph.
    
    Handles:
    - **bold** formatting
    - *italic* formatting
    - Mixed formatting
    """
    # Split text by formatting markers
    # Pattern: find **bold** or *italic* segments
    
    # First, handle bold and italic by splitting into segments
    segments = []
    current_pos = 0
    
    # Find all **bold** and *italic* patterns
    pattern = r'(\*\*[^*]+\*\*|\*[^*]+\*)'
    matches = list(re.finditer(pattern, text))
    
    for match in matches:
        # Add text before the match
        if match.start() > current_pos:
            segments.append(('normal', text[current_pos:match.start()]))
        
        # Add the formatted text
        matched_text = match.group()
        if matched_text.startswith('**') and matched_text.endswith('**'):
            segments.append(('bold', matched_text[2:-2]))
        elif matched_text.startswith('*') and matched_text.endswith('*'):
            segments.append(('italic', matched_text[1:-1]))
        
        current_pos = match.end()
    
    # Add remaining text
    if current_pos < len(text):
        segments.append(('normal', text[current_pos:]))
    
    # If no formatting found, just add normal text
    if not segments:
        segments = [('normal', text)]
    
    # Add runs to paragraph
    for style, segment_text in segments:
        run = paragraph.add_run(segment_text)
        
        if style == 'bold':
            run.bold = True
        elif style == 'italic':
            run.italic = True
        
        # Set font size
        run.font.size = Pt(11)


def _create_table_from_markdown(doc: Document, table_lines: list[str]) -> None:
    """
    Create a DOCX table from Markdown table syntax.
    
    Example Markdown table:
    | Header 1 | Header 2 |
    |----------|----------|
    | Cell 1   | Cell 2   |
    
    Args:
        doc: DOCX Document object
        table_lines: List of lines containing table rows
    """
    if not table_lines:
        return
    
    # Parse header row
    header_row = table_lines[0]
    headers = [cell.strip() for cell in header_row.split('|')[1:-1]]
    
    # Skip separator line (line 1)
    # Parse data rows (lines 2+)
    data_rows = []
    for line in table_lines[2:]:
        if not line.strip():
            continue
        cells = [cell.strip() for cell in line.split('|')[1:-1]]
        data_rows.append(cells)
    
    # Create table
    table = doc.add_table(rows=1 + len(data_rows), cols=len(headers))
    table.style = 'Light Grid Accent 1'
    
    # Add header
    header_cells = table.rows[0].cells
    for i, header_text in enumerate(headers):
        header_cells[i].text = header_text
        # Bold header
        for paragraph in header_cells[i].paragraphs:
            for run in paragraph.runs:
                run.bold = True
    
    # Add data rows
    for row_idx, row_data in enumerate(data_rows):
        row_cells = table.rows[row_idx + 1].cells
        for col_idx, cell_text in enumerate(row_data):
            row_cells[col_idx].text = cell_text
