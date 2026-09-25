"""
Unit tests — export service
Tests: Export generation, document exports (summary/checklist/lawyer_brief), comparison exports, format rendering
Covers: architecture.md §5.8 Export Module
"""

import io
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.export import ExportArtifact
from app.models.document import Document
from app.models.clause import Clause
from app.models.comparison import ComparisonJob, ComparisonResult
from app.services.export import (
    generate_export,
    _generate_document_export,
    _generate_comparison_export,
    _generate_summary_md,
    _generate_checklist_md,
    _generate_lawyer_brief_md,
    _generate_comparison_report_md,
    _get_content_type,
)


class TestGenerateExport:
    """Test generate_export main orchestration function."""

    @pytest.mark.asyncio
    @patch("app.services.export.upload_to_s3")
    @patch("app.services.export.render_to_pdf")
    async def test_generate_export_document_pdf(self, mock_render_pdf, mock_upload):
        """Generate document export in PDF format."""
        db = AsyncMock()
        export_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        
        # Mock export artifact
        export_artifact = ExportArtifact(
            id=export_id,
            owner_id=owner_id,
            document_id=doc_id,
            comparison_job_id=None,
            export_type="summary",
            file_format="pdf",
            status="queued",
        )
        
        # Mock document and clauses
        document = Document(
            id=doc_id,
            owner_id=owner_id,
            original_filename="contract.pdf",
            status="ready",
            page_count=10,
        )
        clause = Clause(
            id=uuid.uuid4(),
            document_id=doc_id,
            clause_type="indemnification",
            text_excerpt="Test clause excerpt",
            risk_level="high",
            risk_rationale="High risk reason",
        )
        
        # Setup DB mocks
        mock_results = []
        
        # Export artifact lookup
        mock_export_result = MagicMock()
        mock_export_result.scalar_one_or_none.return_value = export_artifact
        mock_results.append(mock_export_result)
        
        # Document lookup
        mock_doc_result = MagicMock()
        mock_doc_result.scalar_one_or_none.return_value = document
        mock_results.append(mock_doc_result)
        
        # Clauses lookup
        mock_clauses_result = MagicMock()
        mock_clauses_result.scalars.return_value.all.return_value = [clause]
        mock_results.append(mock_clauses_result)
        
        async def mock_execute(*args, **kwargs):
            return mock_results.pop(0)
        
        db.execute = mock_execute
        
        # Mock PDF rendering
        mock_render_pdf.return_value = io.BytesIO(b"PDF content")
        
        # Act
        storage_key, file_size = await generate_export(db=db, export_id=export_id)
        
        # Assert
        assert storage_key == f"{owner_id}/exports/export_{export_id}.pdf"
        assert file_size > 0
        assert export_artifact.status == "ready"
        assert export_artifact.storage_key == storage_key
        mock_upload.assert_awaited_once()
        db.commit.assert_awaited()
    
    @pytest.mark.asyncio
    @patch("app.services.export.upload_to_s3")
    @patch("app.services.export.render_to_docx")
    async def test_generate_export_document_docx(self, mock_render_docx, mock_upload):
        """Generate document export in DOCX format."""
        db = AsyncMock()
        export_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        
        export_artifact = ExportArtifact(
            id=export_id,
            owner_id=owner_id,
            document_id=doc_id,
            export_type="checklist",
            file_format="docx",
            status="queued",
        )
        
        document = Document(id=doc_id, owner_id=owner_id, original_filename="doc.pdf", status="ready")
        
        # Setup mocks
        mock_results = []
        mock_results.append(MagicMock(scalar_one_or_none=MagicMock(return_value=export_artifact)))
        mock_results.append(MagicMock(scalar_one_or_none=MagicMock(return_value=document)))
        mock_results.append(MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))
        
        async def mock_execute(*args, **kwargs):
            return mock_results.pop(0)
        
        db.execute = mock_execute
        
        mock_render_docx.return_value = io.BytesIO(b"DOCX content")
        
        # Act
        storage_key, file_size = await generate_export(db=db, export_id=export_id)
        
        # Assert
        assert storage_key.endswith(".docx")
        mock_render_docx.assert_called_once()
    
    @pytest.mark.asyncio
    @patch("app.services.export.upload_to_s3")
    @patch("app.services.export.render_to_markdown")
    async def test_generate_export_document_markdown(self, mock_render_md, mock_upload):
        """Generate document export in Markdown format."""
        db = AsyncMock()
        export_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        
        export_artifact = ExportArtifact(
            id=export_id,
            owner_id=owner_id,
            document_id=doc_id,
            export_type="lawyer_brief",
            file_format="md",
            status="queued",
        )
        
        document = Document(id=doc_id, owner_id=owner_id, original_filename="doc.pdf", status="ready")
        
        # Setup mocks
        mock_results = []
        mock_results.append(MagicMock(scalar_one_or_none=MagicMock(return_value=export_artifact)))
        mock_results.append(MagicMock(scalar_one_or_none=MagicMock(return_value=document)))
        mock_results.append(MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))
        
        async def mock_execute(*args, **kwargs):
            return mock_results.pop(0)
        
        db.execute = mock_execute
        
        mock_render_md.return_value = io.BytesIO(b"# Markdown content")
        
        # Act
        storage_key, file_size = await generate_export(db=db, export_id=export_id)
        
        # Assert
        assert storage_key.endswith(".md")
        mock_render_md.assert_called_once()
    
    @pytest.mark.asyncio
    @patch("app.services.export.upload_to_s3")
    @patch("app.services.export.render_to_pdf")
    async def test_generate_export_comparison(self, mock_render_pdf, mock_upload):
        """Generate comparison export."""
        db = AsyncMock()
        export_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        job_id = uuid.uuid4()
        
        export_artifact = ExportArtifact(
            id=export_id,
            owner_id=owner_id,
            document_id=None,
            comparison_job_id=job_id,
            export_type="comparison_report",
            file_format="pdf",
            status="queued",
        )
        
        job = ComparisonJob(id=job_id, owner_id=owner_id, status="completed")
        
        # Setup mocks
        mock_results = []
        mock_results.append(MagicMock(scalar_one_or_none=MagicMock(return_value=export_artifact)))
        mock_results.append(MagicMock(scalar_one_or_none=MagicMock(return_value=job)))
        mock_results.append(MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))
        
        async def mock_execute(*args, **kwargs):
            return mock_results.pop(0)
        
        db.execute = mock_execute
        
        mock_render_pdf.return_value = io.BytesIO(b"Comparison PDF")
        
        # Act
        storage_key, file_size = await generate_export(db=db, export_id=export_id)
        
        # Assert
        assert storage_key == f"{owner_id}/exports/export_{export_id}.pdf"
        assert export_artifact.status == "ready"
    
    @pytest.mark.asyncio
    async def test_generate_export_not_found(self):
        """Raise error if export artifact not found."""
        db = AsyncMock()
        export_id = uuid.uuid4()
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        
        async def mock_execute(*args, **kwargs):
            return mock_result
        
        db.execute = mock_execute
        
        with pytest.raises(ValueError, match="not found"):
            await generate_export(db=db, export_id=export_id)
    
    @pytest.mark.asyncio
    async def test_generate_export_missing_source(self):
        """Raise error if export has no document_id or comparison_job_id."""
        db = AsyncMock()
        export_id = uuid.uuid4()
        
        export_artifact = ExportArtifact(
            id=export_id,
            owner_id=uuid.uuid4(),
            document_id=None,
            comparison_job_id=None,  # Both missing!
            export_type="summary",
            file_format="pdf",
            status="queued",
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = export_artifact
        
        async def mock_execute(*args, **kwargs):
            return mock_result
        
        db.execute = mock_execute
        
        with pytest.raises(ValueError, match="must have document_id or comparison_job_id"):
            await generate_export(db=db, export_id=export_id)
    
    @pytest.mark.asyncio
    @patch("app.services.export.upload_to_s3")
    @patch("app.services.export.render_to_pdf")
    async def test_generate_export_updates_status_to_failed_on_error(self, mock_render_pdf, mock_upload):
        """Export status updated to failed if error occurs."""
        db = AsyncMock()
        export_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        
        export_artifact = ExportArtifact(
            id=export_id,
            owner_id=uuid.uuid4(),
            document_id=doc_id,
            export_type="summary",
            file_format="pdf",
            status="queued",
        )
        
        # Setup mocks
        mock_results = []
        mock_results.append(MagicMock(scalar_one_or_none=MagicMock(return_value=export_artifact)))
        mock_results.append(MagicMock(scalar_one_or_none=MagicMock(return_value=None)))  # Document not found
        
        async def mock_execute(*args, **kwargs):
            return mock_results.pop(0)
        
        db.execute = mock_execute
        
        # Act & Assert
        with pytest.raises(ValueError, match="not found"):
            await generate_export(db=db, export_id=export_id)
        
        # Verify status updated to failed
        assert export_artifact.status == "failed"


class TestGenerateDocumentExport:
    """Test _generate_document_export for summary/checklist/lawyer_brief."""

    @pytest.mark.asyncio
    async def test_generate_summary_export(self):
        """Generate summary export."""
        db = AsyncMock()
        doc_id = uuid.uuid4()
        
        document = Document(
            id=doc_id,
            owner_id=uuid.uuid4(),
            original_filename="contract.pdf",
            status="ready",
            page_count=5,
        )
        
        clause = Clause(
            id=uuid.uuid4(),
            document_id=doc_id,
            clause_type="termination",
            text_excerpt="Termination clause text",
            risk_level="high",
            risk_rationale="Short termination notice",
        )
        
        # Setup mocks
        mock_results = []
        mock_results.append(MagicMock(scalar_one_or_none=MagicMock(return_value=document)))
        mock_results.append(MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[clause])))))
        
        async def mock_execute(*args, **kwargs):
            return mock_results.pop(0)
        
        db.execute = mock_execute
        
        # Act
        content = await _generate_document_export(
            db=db,
            document_id=doc_id,
            export_type="summary",
            file_format="pdf",
        )
        
        # Assert
        assert "Document Summary" in content
        assert "contract.pdf" in content
        assert "High Risk Clauses" in content
        assert "Termination" in content
    
    @pytest.mark.asyncio
    async def test_generate_checklist_export(self):
        """Generate checklist export."""
        db = AsyncMock()
        doc_id = uuid.uuid4()
        
        document = Document(id=doc_id, owner_id=uuid.uuid4(), original_filename="doc.pdf", status="ready")
        
        clauses = [
            Clause(id=uuid.uuid4(), document_id=doc_id, clause_type="payment", text_excerpt="Pay text", risk_level="medium"),
            Clause(id=uuid.uuid4(), document_id=doc_id, clause_type="payment", text_excerpt="More pay", risk_level="low"),
        ]
        
        # Setup mocks
        mock_results = []
        mock_results.append(MagicMock(scalar_one_or_none=MagicMock(return_value=document)))
        mock_results.append(MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=clauses)))))
        
        async def mock_execute(*args, **kwargs):
            return mock_results.pop(0)
        
        db.execute = mock_execute
        
        # Act
        content = await _generate_document_export(
            db=db,
            document_id=doc_id,
            export_type="checklist",
            file_format="md",
        )
        
        # Assert
        assert "Action Checklist" in content
        assert "Review Priorities" in content
        assert "Payment" in content
        assert "- [ ]" in content  # Checkbox
    
    @pytest.mark.asyncio
    async def test_generate_lawyer_brief_export(self):
        """Generate lawyer brief export."""
        db = AsyncMock()
        doc_id = uuid.uuid4()
        
        document = Document(id=doc_id, owner_id=uuid.uuid4(), original_filename="agreement.pdf", status="ready")
        
        clause = Clause(
            id=uuid.uuid4(),
            document_id=doc_id,
            clause_type="liability",
            text_excerpt="Liability text",
            risk_level="high",
            risk_rationale="Broad liability exposure",
        )
        
        # Setup mocks
        mock_results = []
        mock_results.append(MagicMock(scalar_one_or_none=MagicMock(return_value=document)))
        mock_results.append(MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[clause])))))
        
        async def mock_execute(*args, **kwargs):
            return mock_results.pop(0)
        
        db.execute = mock_execute
        
        # Act
        content = await _generate_document_export(
            db=db,
            document_id=doc_id,
            export_type="lawyer_brief",
            file_format="docx",
        )
        
        # Assert
        assert "Questions for Your Lawyer" in content
        assert "High Priority Items" in content
        assert "Liability" in content
        assert "How does this clause affect" in content
    
    @pytest.mark.asyncio
    async def test_generate_document_export_invalid_type(self):
        """Raise error for unknown export type."""
        db = AsyncMock()
        doc_id = uuid.uuid4()
        
        document = Document(id=doc_id, owner_id=uuid.uuid4(), original_filename="doc.pdf", status="ready")
        
        mock_results = []
        mock_results.append(MagicMock(scalar_one_or_none=MagicMock(return_value=document)))
        mock_results.append(MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))
        
        async def mock_execute(*args, **kwargs):
            return mock_results.pop(0)
        
        db.execute = mock_execute
        
        with pytest.raises(ValueError, match="Unknown export type"):
            await _generate_document_export(
                db=db,
                document_id=doc_id,
                export_type="invalid_type",
                file_format="pdf",
            )


class TestGenerateComparisonExport:
    """Test _generate_comparison_export."""

    @pytest.mark.asyncio
    async def test_generate_comparison_export(self):
        """Generate comparison report export."""
        db = AsyncMock()
        job_id = uuid.uuid4()
        
        job = ComparisonJob(id=job_id, owner_id=uuid.uuid4(), status="completed")
        
        result = ComparisonResult(
            id=uuid.uuid4(),
            comparison_job_id=job_id,
            clause_type="indemnification",
            excerpts_by_document={"doc1": "Excerpt 1", "doc2": "Excerpt 2"},
            diff_summary="Document 2 has broader scope",
            materiality="significant",
        )
        
        # Setup mocks
        mock_results = []
        mock_results.append(MagicMock(scalar_one_or_none=MagicMock(return_value=job)))
        mock_results.append(MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[result])))))
        
        async def mock_execute(*args, **kwargs):
            return mock_results.pop(0)
        
        db.execute = mock_execute
        
        # Act
        content = await _generate_comparison_export(
            db=db,
            comparison_job_id=job_id,
            file_format="pdf",
        )
        
        # Assert
        assert "Document Comparison Report" in content
        assert "Indemnification" in content
        assert "significant" in content.lower()
        assert "broader scope" in content


class TestMarkdownGenerators:
    """Test Markdown generation helper functions."""

    def test_generate_summary_md(self):
        """Generate summary markdown."""
        doc = Document(
            id=uuid.uuid4(),
            owner_id=uuid.uuid4(),
            original_filename="test.pdf",
            status="ready",
            page_count=10,
        )
        
        clauses = [
            Clause(
                id=uuid.uuid4(),
                document_id=doc.id,
                clause_type="termination",
                text_excerpt="Term text " * 50,  # Long text
                risk_level="high",
                risk_rationale="Short notice period",
            ),
            Clause(
                id=uuid.uuid4(),
                document_id=doc.id,
                clause_type="payment",
                text_excerpt="Pay text",
                risk_level="medium",
                risk_rationale="Unclear terms",
            ),
        ]
        
        # Act
        md = _generate_summary_md(doc, clauses)
        
        # Assert
        assert "Document Summary: test.pdf" in md
        assert "High Risk Clauses: 1" in md
        assert "Medium Risk Clauses: 1" in md
        assert "Termination" in md
        assert "Short notice period" in md
    
    def test_generate_checklist_md(self):
        """Generate checklist markdown."""
        doc = Document(id=uuid.uuid4(), owner_id=uuid.uuid4(), original_filename="doc.pdf", status="ready")
        
        clauses = [
            Clause(id=uuid.uuid4(), document_id=doc.id, clause_type="indemnification", text_excerpt="Test", risk_level="high"),
            Clause(id=uuid.uuid4(), document_id=doc.id, clause_type="indemnification", text_excerpt="Test2", risk_level="low"),
            Clause(id=uuid.uuid4(), document_id=doc.id, clause_type="warranty", text_excerpt="Warranty", risk_level="medium"),
        ]
        
        # Act
        md = _generate_checklist_md(doc, clauses)
        
        # Assert
        assert "Action Checklist" in md
        assert "- [ ] **Indemnification** (2 clauses) — ⚠️ 1 high risk" in md
        assert "- [ ] **Warranty** (1 clause)" in md
    
    def test_generate_lawyer_brief_md(self):
        """Generate lawyer brief markdown."""
        doc = Document(id=uuid.uuid4(), owner_id=uuid.uuid4(), original_filename="contract.pdf", status="ready")
        
        clauses = [
            Clause(
                id=uuid.uuid4(),
                document_id=doc.id,
                clause_type="liability",
                text_excerpt="Liability clause",
                risk_level="high",
                risk_rationale="Unlimited liability",
            ),
            Clause(
                id=uuid.uuid4(),
                document_id=doc.id,
                clause_type="termination",
                text_excerpt="Termination clause",
                risk_level="high",
                risk_rationale="No notice required",
            ),
        ]
        
        # Act
        md = _generate_lawyer_brief_md(doc, clauses)
        
        # Assert
        assert "Questions for Your Lawyer" in md
        assert "High Priority Items" in md
        assert "1. **Liability**" in md
        assert "2. **Termination**" in md
        assert "Unlimited liability" in md
        assert "No notice required" in md
    
    def test_generate_comparison_report_md(self):
        """Generate comparison report markdown."""
        results = [
            ComparisonResult(
                id=uuid.uuid4(),
                comparison_job_id=uuid.uuid4(),
                clause_type="payment_terms",
                excerpts_by_document={
                    "doc1-uuid": "Net 30 payment terms",
                    "doc2-uuid": "Net 60 payment terms",
                },
                diff_summary="Document 2 allows 30 more days to pay",
                materiality="significant",
            ),
            ComparisonResult(
                id=uuid.uuid4(),
                comparison_job_id=uuid.uuid4(),
                clause_type="warranty",
                excerpts_by_document={
                    "doc1-uuid": "90 day warranty",
                    "doc2-uuid": "90 day warranty",
                },
                diff_summary="Identical warranty terms",
                materiality="none",
            ),
        ]
        
        # Act
        md = _generate_comparison_report_md(results)
        
        # Assert
        assert "Document Comparison Report" in md
        assert "Differences Found: 2" in md
        assert "**Significant**: 1" in md
        assert "**None**: 1" in md
        assert "Payment Terms" in md
        assert "30 more days to pay" in md
        assert "🟠" in md  # Significant icon
        assert "🟢" in md  # None icon


class TestContentType:
    """Test _get_content_type helper."""

    def test_get_content_type_pdf(self):
        """PDF content type."""
        assert _get_content_type("pdf") == "application/pdf"
    
    def test_get_content_type_docx(self):
        """DOCX content type."""
        assert _get_content_type("docx") == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    
    def test_get_content_type_markdown(self):
        """Markdown content type."""
        assert _get_content_type("md") == "text/markdown"
    
    def test_get_content_type_unknown(self):
        """Unknown format returns octet-stream."""
        assert _get_content_type("xyz") == "application/octet-stream"
