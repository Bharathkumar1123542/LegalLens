"""
Export service — LegalLens Phase 5
Implements: architecture.md §5.8 Export Module.
Functions: generate_export() for summary/checklist/lawyer_brief/comparison_report.
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.export import ExportArtifact
from app.models.document import Document
from app.models.clause import Clause
from app.models.comparison import ComparisonJob, ComparisonResult
from app.services.storage import upload_to_s3
from app.services.renderers import render_to_pdf, render_to_docx, render_to_markdown

logger = logging.getLogger(__name__)


async def generate_export(
    db: AsyncSession,
    export_id: uuid.UUID,
) -> tuple[str, int]:
    """
    Generate export artifact and upload to S3.
    
    Per architecture.md §5.8:
    - Assembles data from persisted structured data
    - Renders to requested file format (PDF/DOCX/Markdown)
    - Uploads to S3 and returns storage key
    
    Args:
        db: Database session
        export_id: Export artifact ID
    
    Returns:
        Tuple of (storage_key, file_size_bytes)
    
    Raises:
        ValueError: If export not found or source data unavailable
    """
    # Get export artifact
    result = await db.execute(
        select(ExportArtifact).where(ExportArtifact.id == export_id)
    )
    export_artifact = result.scalar_one_or_none()
    
    if not export_artifact:
        raise ValueError(f"Export artifact {export_id} not found")
    
    # Update status to generating
    export_artifact.status = "generating"
    await db.commit()
    
    try:
        # Generate Markdown content based on export type
        if export_artifact.document_id:
            markdown_content = await _generate_document_export(
                db,
                export_artifact.document_id,
                export_artifact.export_type,
                export_artifact.file_format,
            )
        elif export_artifact.comparison_job_id:
            markdown_content = await _generate_comparison_export(
                db,
                export_artifact.comparison_job_id,
                export_artifact.file_format,
            )
        else:
            raise ValueError("Export must have document_id or comparison_job_id")
        
        # Render to requested format
        if export_artifact.file_format == "pdf":
            content_bytes = render_to_pdf(markdown_content)
        elif export_artifact.file_format == "docx":
            content_bytes = render_to_docx(markdown_content)
        else:  # md
            content_bytes = render_to_markdown(markdown_content)
        
        # Generate storage key
        filename = f"export_{export_id}.{export_artifact.file_format}"
        storage_key = f"{export_artifact.owner_id}/exports/{filename}"
        
        # Upload to S3
        await upload_to_s3(
            key=storage_key,
            data=content_bytes,
            content_type=_get_content_type(export_artifact.file_format),
        )
        
        # Update export artifact
        export_artifact.status = "ready"
        export_artifact.storage_key = storage_key
        await db.commit()
        
        logger.info(
            f"export.generated: export={export_id}, "
            f"type={export_artifact.export_type}, "
            f"format={export_artifact.file_format}, "
            f"size={len(content_bytes)} bytes"
        )
        
        return storage_key, len(content_bytes)
        
    except Exception as e:
        export_artifact.status = "failed"
        await db.commit()
        
        logger.error(f"export.failed: export={export_id}, error={e}")
        raise


async def _generate_document_export(
    db: AsyncSession,
    document_id: uuid.UUID,
    export_type: str,
    file_format: str,
) -> str:
    """
    Generate export for a single document.
    
    Supports: summary, checklist, lawyer_brief
    """
    # Get document
    doc_result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = doc_result.scalar_one_or_none()
    
    if not document:
        raise ValueError(f"Document {document_id} not found")
    
    # Get clauses
    clauses_result = await db.execute(
        select(Clause)
        .where(Clause.document_id == document_id)
        .order_by(Clause.clause_type, Clause.risk_level.desc())
    )
    clauses = clauses_result.scalars().all()
    
    # Generate content based on type (Markdown format)
    if export_type == "summary":
        content = _generate_summary_md(document, clauses)
    elif export_type == "checklist":
        content = _generate_checklist_md(document, clauses)
    elif export_type == "lawyer_brief":
        content = _generate_lawyer_brief_md(document, clauses)
    else:
        raise ValueError(f"Unknown export type: {export_type}")
    
    # Note: PDF/DOCX rendering would happen here
    # For MVP, we return Markdown format
    return content


async def _generate_comparison_export(
    db: AsyncSession,
    comparison_job_id: uuid.UUID,
    file_format: str,
) -> str:
    """Generate comparison report export."""
    # Get comparison job
    job_result = await db.execute(
        select(ComparisonJob).where(ComparisonJob.id == comparison_job_id)
    )
    job = job_result.scalar_one_or_none()
    
    if not job:
        raise ValueError(f"Comparison job {comparison_job_id} not found")
    
    # Get comparison results
    results_query = await db.execute(
        select(ComparisonResult)
        .where(ComparisonResult.comparison_job_id == comparison_job_id)
        .order_by(ComparisonResult.materiality.desc(), ComparisonResult.clause_type)
    )
    results = results_query.scalars().all()
    
    # Generate comparison report (Markdown)
    content = _generate_comparison_report_md(results)
    
    return content


def _generate_summary_md(document: Document, clauses: list[Clause]) -> str:
    """Generate document summary in Markdown."""
    high_risk = [c for c in clauses if c.risk_level == "high"]
    medium_risk = [c for c in clauses if c.risk_level == "medium"]
    
    md = f"""# Document Summary: {document.original_filename}

**Date**: {datetime.now().strftime("%Y-%m-%d")}  
**Document ID**: {document.id}  
**Page Count**: {document.page_count or "N/A"}

## Risk Overview

- **High Risk Clauses**: {len(high_risk)}
- **Medium Risk Clauses**: {len(medium_risk)}
- **Total Clauses Extracted**: {len(clauses)}

## High Risk Clauses

"""
    for clause in high_risk:
        md += f"### {clause.clause_type.replace('_', ' ').title()}\n\n"
        md += f"**Risk Rationale**: {clause.risk_rationale}\n\n"
        md += f"**Excerpt**: {clause.text_excerpt[:200]}...\n\n"
    
    md += "\n---\n\n*This summary is for informational purposes only and does not constitute legal advice.*"
    
    return md


def _generate_checklist_md(document: Document, clauses: list[Clause]) -> str:
    """Generate action checklist in Markdown."""
    md = f"""# Action Checklist: {document.original_filename}

**Date**: {datetime.now().strftime("%Y-%m-%d")}

## Review Priorities

"""
    
    # Group by clause type
    by_type = {}
    for clause in clauses:
        if clause.clause_type not in by_type:
            by_type[clause.clause_type] = []
        by_type[clause.clause_type].append(clause)
    
    for clause_type, type_clauses in sorted(by_type.items()):
        high_risk_count = sum(1 for c in type_clauses if c.risk_level == "high")
        md += f"- [ ] **{clause_type.replace('_', ' ').title()}** "
        md += f"({len(type_clauses)} clause{'s' if len(type_clauses) > 1 else ''})"
        if high_risk_count:
            md += f" — ⚠️ {high_risk_count} high risk"
        md += "\n"
    
    md += "\n---\n\n*Consult with legal counsel before taking action.*"
    
    return md


def _generate_lawyer_brief_md(document: Document, clauses: list[Clause]) -> str:
    """Generate lawyer preparation brief in Markdown."""
    high_risk = [c for c in clauses if c.risk_level == "high"]
    
    md = f"""# Questions for Your Lawyer: {document.original_filename}

**Date**: {datetime.now().strftime("%Y-%m-%d")}

## High Priority Items

"""
    
    for i, clause in enumerate(high_risk, 1):
        md += f"{i}. **{clause.clause_type.replace('_', ' ').title()}**\n"
        md += f"   - {clause.risk_rationale}\n"
        md += f"   - Question: How does this clause affect my obligations?\n\n"
    
    md += "\n## General Questions\n\n"
    md += "- What are my termination rights under this agreement?\n"
    md += "- Are there any unusual liability provisions?\n"
    md += "- What are my obligations if I want to exit this agreement?\n"
    
    md += "\n---\n\n*Bring this brief to your attorney consultation.*"
    
    return md


def _generate_comparison_report_md(results: list[ComparisonResult]) -> str:
    """Generate comparison report in Markdown."""
    md = f"""# Document Comparison Report

**Date**: {datetime.now().strftime("%Y-%m-%d")}  
**Differences Found**: {len(results)}

## Summary

"""
    
    # Count by materiality
    by_materiality = {"critical": 0, "significant": 0, "minor": 0, "none": 0}
    for result in results:
        by_materiality[result.materiality] = by_materiality.get(result.materiality, 0) + 1
    
    md += f"- **Critical**: {by_materiality['critical']}\n"
    md += f"- **Significant**: {by_materiality['significant']}\n"
    md += f"- **Minor**: {by_materiality['minor']}\n"
    md += f"- **None**: {by_materiality['none']}\n\n"
    
    md += "## Detailed Comparison\n\n"
    
    for result in results:
        icon = {"critical": "🔴", "significant": "🟠", "minor": "🟡", "none": "🟢"}
        md += f"### {icon.get(result.materiality, '')} {result.clause_type.replace('_', ' ').title()}\n\n"
        md += f"**Materiality**: {result.materiality.upper()}\n\n"
        md += f"**Summary**: {result.diff_summary}\n\n"
        
        md += "**Excerpts**:\n\n"
        for doc_id, excerpt in result.excerpts_by_document.items():
            md += f"- Document {doc_id[:8]}...: {excerpt[:150]}...\n"
        md += "\n"
    
    md += "\n---\n\n*This comparison is for informational purposes only.*"
    
    return md


def _get_content_type(file_format: str) -> str:
    """Get MIME type for file format."""
    formats = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "md": "text/markdown",
    }
    return formats.get(file_format, "application/octet-stream")
