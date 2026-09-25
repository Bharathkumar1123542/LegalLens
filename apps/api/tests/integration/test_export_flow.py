"""
Integration tests — Export flow (Phase 5)
Tests: POST /exports, GET /exports/:id, full export pipeline with renderers
Covers: architecture.md §5.8 Export Module with real DB
"""

import io
import uuid
from unittest.mock import patch, AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.clause import Clause
from app.models.comparison import ComparisonJob, ComparisonResult
from app.models.export import ExportArtifact
from app.models.user import User


@pytest.mark.asyncio
class TestExportEndpoints:
    """Test export API endpoints with real database."""

    async def test_create_document_export_summary(
        self,
        async_client,
        db_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """POST /exports creates summary export for document."""
        # Create document with clauses
        doc = Document(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            original_filename="contract.pdf",
            mime_type="application/pdf",
            file_size_bytes=5000,
            storage_key=f"{test_user.id}/contract.pdf",
            file_hash_sha256="a" * 64,
            status="ready",
            page_count=10,
        )
        db_session.add(doc)
        await db_session.commit()
        
        clause = Clause(
            id=uuid.uuid4(),
            document_id=doc.id,
            clause_type="termination",
            text_excerpt="30 day termination notice required",
            risk_level="high",
            risk_rationale="Short notice period",
        )
        db_session.add(clause)
        await db_session.commit()
        
        # Create export
        payload = {
            "document_id": str(doc.id),
            "export_type": "summary",
            "file_format": "pdf",
        }
        
        response = await async_client.post(
            "/api/v1/exports",
            json=payload,
            headers=auth_headers,
        )
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["status"] == "queued"
        assert data["export_type"] == "summary"
        assert data["file_format"] == "pdf"
        
        # Verify database
        export_id = uuid.UUID(data["id"])
        result = await db_session.execute(
            select(ExportArtifact).where(ExportArtifact.id == export_id)
        )
        export_artifact = result.scalar_one()
        assert export_artifact.document_id == doc.id
        assert export_artifact.status == "queued"
    
    async def test_create_document_export_checklist(
        self,
        async_client,
        db_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """POST /exports creates checklist export."""
        doc = Document(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            original_filename="doc.pdf",
            mime_type="application/pdf",
            file_size_bytes=1000,
            storage_key=f"{test_user.id}/doc.pdf",
            file_hash_sha256="b" * 64,
            status="ready",
        )
        db_session.add(doc)
        await db_session.commit()
        
        payload = {
            "document_id": str(doc.id),
            "export_type": "checklist",
            "file_format": "docx",
        }
        
        response = await async_client.post(
            "/api/v1/exports",
            json=payload,
            headers=auth_headers,
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["export_type"] == "checklist"
        assert data["file_format"] == "docx"
    
    async def test_create_document_export_lawyer_brief(
        self,
        async_client,
        db_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """POST /exports creates lawyer brief export."""
        doc = Document(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            original_filename="agreement.pdf",
            mime_type="application/pdf",
            file_size_bytes=2000,
            storage_key=f"{test_user.id}/agreement.pdf",
            file_hash_sha256="c" * 64,
            status="ready",
        )
        db_session.add(doc)
        await db_session.commit()
        
        payload = {
            "document_id": str(doc.id),
            "export_type": "lawyer_brief",
            "file_format": "md",
        }
        
        response = await async_client.post(
            "/api/v1/exports",
            json=payload,
            headers=auth_headers,
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["export_type"] == "lawyer_brief"
        assert data["file_format"] == "md"
    
    async def test_create_comparison_export(
        self,
        async_client,
        db_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """POST /exports creates comparison report export."""
        # Create comparison job
        job = ComparisonJob(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            status="completed",
        )
        db_session.add(job)
        await db_session.commit()
        
        # Create comparison result
        result = ComparisonResult(
            id=uuid.uuid4(),
            comparison_job_id=job.id,
            clause_type="payment_terms",
            excerpts_by_document={"doc1": "Net 30", "doc2": "Net 60"},
            diff_summary="Different payment terms",
            materiality="significant",
        )
        db_session.add(result)
        await db_session.commit()
        
        # Create export
        payload = {
            "comparison_job_id": str(job.id),
            "export_type": "comparison_report",
            "file_format": "pdf",
        }
        
        response = await async_client.post(
            "/api/v1/exports",
            json=payload,
            headers=auth_headers,
        )
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["export_type"] == "comparison_report"
        
        # Verify database
        export_id = uuid.UUID(data["id"])
        db_result = await db_session.execute(
            select(ExportArtifact).where(ExportArtifact.id == export_id)
        )
        export_artifact = db_result.scalar_one()
        assert export_artifact.comparison_job_id == job.id
    
    async def test_create_export_validates_ownership(
        self,
        async_client,
        db_session: AsyncSession,
        test_user: User,
        another_user: User,
        auth_headers: dict,
    ):
        """Reject export if user doesn't own document."""
        # Document owned by another_user
        doc = Document(
            id=uuid.uuid4(),
            owner_id=another_user.id,
            original_filename="theirs.pdf",
            mime_type="application/pdf",
            file_size_bytes=1000,
            storage_key=f"{another_user.id}/theirs.pdf",
            file_hash_sha256="x" * 64,
            status="ready",
        )
        db_session.add(doc)
        await db_session.commit()
        
        payload = {
            "document_id": str(doc.id),
            "export_type": "summary",
            "file_format": "pdf",
        }
        
        response = await async_client.post(
            "/api/v1/exports",
            json=payload,
            headers=auth_headers,
        )
        
        assert response.status_code == 404  # Not found (ownership)
    
    async def test_get_export_success(
        self,
        async_client,
        db_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """GET /exports/:id returns export artifact details."""
        doc = Document(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            original_filename="doc.pdf",
            mime_type="application/pdf",
            file_size_bytes=1000,
            storage_key=f"{test_user.id}/doc.pdf",
            file_hash_sha256="a" * 64,
            status="ready",
        )
        db_session.add(doc)
        await db_session.commit()
        
        # Create export artifact
        export = ExportArtifact(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            document_id=doc.id,
            export_type="summary",
            file_format="pdf",
            status="ready",
            storage_key=f"{test_user.id}/exports/export.pdf",
        )
        db_session.add(export)
        await db_session.commit()
        
        # Get export
        response = await async_client.get(
            f"/api/v1/exports/{export.id}",
            headers=auth_headers,
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(export.id)
        assert data["status"] == "ready"
        assert data["export_type"] == "summary"
        assert "download_url" in data
    
    async def test_get_export_not_found(
        self,
        async_client,
        auth_headers: dict,
    ):
        """GET /exports/:id returns 404 for nonexistent export."""
        fake_id = uuid.uuid4()
        response = await async_client.get(
            f"/api/v1/exports/{fake_id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 404
    
    async def test_get_export_enforces_ownership(
        self,
        async_client,
        db_session: AsyncSession,
        test_user: User,
        another_user: User,
        other_auth_headers: dict,
    ):
        """User cannot access another user's export."""
        doc = Document(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            original_filename="doc.pdf",
            mime_type="application/pdf",
            file_size_bytes=1000,
            storage_key=f"{test_user.id}/doc.pdf",
            file_hash_sha256="a" * 64,
            status="ready",
        )
        db_session.add(doc)
        await db_session.commit()
        
        export = ExportArtifact(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            document_id=doc.id,
            export_type="summary",
            file_format="pdf",
            status="ready",
        )
        db_session.add(export)
        await db_session.commit()
        
        # Try to access with another_user
        response = await async_client.get(
            f"/api/v1/exports/{export.id}",
            headers=other_auth_headers,
        )
        
        assert response.status_code == 404


@pytest.mark.asyncio
class TestExportWorkerIntegration:
    """Test export worker with real database."""

    @patch("app.services.export.upload_to_s3")
    @patch("app.services.export.render_to_pdf")
    async def test_generate_export_full_flow(
        self,
        mock_render_pdf,
        mock_upload_s3,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Full export flow: create artifact → generate → upload → verify."""
        # Create document with clauses
        doc = Document(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            original_filename="contract.pdf",
            mime_type="application/pdf",
            file_size_bytes=5000,
            storage_key=f"{test_user.id}/contract.pdf",
            file_hash_sha256="a" * 64,
            status="ready",
            page_count=15,
        )
        db_session.add(doc)
        await db_session.commit()
        
        clauses = [
            Clause(
                id=uuid.uuid4(),
                document_id=doc.id,
                clause_type="termination",
                text_excerpt="Short termination notice",
                risk_level="high",
                risk_rationale="Only 7 days notice",
            ),
            Clause(
                id=uuid.uuid4(),
                document_id=doc.id,
                clause_type="payment",
                text_excerpt="Payment in 30 days",
                risk_level="medium",
                risk_rationale="Standard payment terms",
            ),
        ]
        for clause in clauses:
            db_session.add(clause)
        await db_session.commit()
        
        # Create export artifact
        export = ExportArtifact(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            document_id=doc.id,
            export_type="summary",
            file_format="pdf",
            status="queued",
        )
        db_session.add(export)
        await db_session.commit()
        
        # Mock renderers and storage
        mock_render_pdf.return_value = io.BytesIO(b"PDF content bytes")
        mock_upload_s3.return_value = AsyncMock()
        
        # Run export generation
        from app.services.export import generate_export
        storage_key, file_size = await generate_export(
            db=db_session,
            export_id=export.id,
        )
        
        # Verify results
        assert storage_key == f"{test_user.id}/exports/export_{export.id}.pdf"
        assert file_size > 0
        
        # Check database updated
        await db_session.refresh(export)
        assert export.status == "ready"
        assert export.storage_key == storage_key
        
        # Verify S3 upload called
        mock_upload_s3.assert_awaited_once()
        upload_kwargs = mock_upload_s3.call_args.kwargs
        assert upload_kwargs["key"] == storage_key
        assert upload_kwargs["content_type"] == "application/pdf"
    
    @patch("app.services.export.upload_to_s3")
    @patch("app.services.export.render_to_docx")
    async def test_generate_export_docx_format(
        self,
        mock_render_docx,
        mock_upload_s3,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Generate export in DOCX format."""
        doc = Document(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            original_filename="doc.pdf",
            mime_type="application/pdf",
            file_size_bytes=1000,
            storage_key=f"{test_user.id}/doc.pdf",
            file_hash_sha256="b" * 64,
            status="ready",
        )
        db_session.add(doc)
        await db_session.commit()
        
        export = ExportArtifact(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            document_id=doc.id,
            export_type="checklist",
            file_format="docx",
            status="queued",
        )
        db_session.add(export)
        await db_session.commit()
        
        mock_render_docx.return_value = io.BytesIO(b"DOCX content")
        mock_upload_s3.return_value = AsyncMock()
        
        from app.services.export import generate_export
        storage_key, file_size = await generate_export(
            db=db_session,
            export_id=export.id,
        )
        
        assert storage_key.endswith(".docx")
        mock_render_docx.assert_called_once()
        
        # Verify content type
        upload_kwargs = mock_upload_s3.call_args.kwargs
        assert "wordprocessingml" in upload_kwargs["content_type"]
    
    @patch("app.services.export.upload_to_s3")
    @patch("app.services.export.render_to_markdown")
    async def test_generate_export_markdown_format(
        self,
        mock_render_md,
        mock_upload_s3,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Generate export in Markdown format."""
        doc = Document(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            original_filename="doc.pdf",
            mime_type="application/pdf",
            file_size_bytes=1000,
            storage_key=f"{test_user.id}/doc.pdf",
            file_hash_sha256="c" * 64,
            status="ready",
        )
        db_session.add(doc)
        await db_session.commit()
        
        export = ExportArtifact(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            document_id=doc.id,
            export_type="lawyer_brief",
            file_format="md",
            status="queued",
        )
        db_session.add(export)
        await db_session.commit()
        
        mock_render_md.return_value = io.BytesIO(b"# Markdown content")
        mock_upload_s3.return_value = AsyncMock()
        
        from app.services.export import generate_export
        storage_key, file_size = await generate_export(
            db=db_session,
            export_id=export.id,
        )
        
        assert storage_key.endswith(".md")
        mock_render_md.assert_called_once()
        
        upload_kwargs = mock_upload_s3.call_args.kwargs
        assert upload_kwargs["content_type"] == "text/markdown"
    
    @patch("app.services.export.upload_to_s3")
    @patch("app.services.export.render_to_pdf")
    async def test_generate_comparison_export_full_flow(
        self,
        mock_render_pdf,
        mock_upload_s3,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Generate comparison report export."""
        # Create comparison job
        job = ComparisonJob(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            status="completed",
        )
        db_session.add(job)
        await db_session.commit()
        
        # Create comparison results
        results = [
            ComparisonResult(
                id=uuid.uuid4(),
                comparison_job_id=job.id,
                clause_type="indemnification",
                excerpts_by_document={"doc1": "Basic indemnity", "doc2": "Broad indemnity"},
                diff_summary="Document 2 has broader indemnification",
                materiality="significant",
            ),
            ComparisonResult(
                id=uuid.uuid4(),
                comparison_job_id=job.id,
                clause_type="liability",
                excerpts_by_document={"doc1": "Limited liability", "doc2": "Unlimited liability"},
                diff_summary="Document 2 has no liability cap",
                materiality="critical",
            ),
        ]
        for result in results:
            db_session.add(result)
        await db_session.commit()
        
        # Create export
        export = ExportArtifact(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            comparison_job_id=job.id,
            export_type="comparison_report",
            file_format="pdf",
            status="queued",
        )
        db_session.add(export)
        await db_session.commit()
        
        mock_render_pdf.return_value = io.BytesIO(b"Comparison PDF")
        mock_upload_s3.return_value = AsyncMock()
        
        from app.services.export import generate_export
        storage_key, file_size = await generate_export(
            db=db_session,
            export_id=export.id,
        )
        
        assert storage_key.startswith(str(test_user.id))
        assert "exports" in storage_key
        
        await db_session.refresh(export)
        assert export.status == "ready"
