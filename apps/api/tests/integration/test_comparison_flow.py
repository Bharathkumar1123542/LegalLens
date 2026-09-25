"""
Integration tests — Comparison flow (Phase 5)
Tests: POST /comparisons, GET /comparisons/:id, full comparison pipeline
Covers: architecture.md §5.6 Comparison Engine with real DB
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.clause import Clause
from app.models.comparison import ComparisonJob, ComparisonJobDocument, ComparisonResult
from app.models.user import User


@pytest.mark.asyncio
class TestComparisonEndpoints:
    """Test comparison API endpoints with real database."""

    async def test_create_comparison_success(
        self,
        async_client,
        db_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """POST /comparisons creates comparison job for valid documents."""
        # Create 2 ready documents
        doc1 = Document(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            original_filename="contract_v1.pdf",
            mime_type="application/pdf",
            file_size_bytes=5000,
            storage_key=f"{test_user.id}/doc1.pdf",
            file_hash_sha256="a" * 64,
            status="ready",
        )
        doc2 = Document(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            original_filename="contract_v2.pdf",
            mime_type="application/pdf",
            file_size_bytes=6000,
            storage_key=f"{test_user.id}/doc2.pdf",
            file_hash_sha256="b" * 64,
            status="ready",
        )
        db_session.add(doc1)
        db_session.add(doc2)
        await db_session.commit()
        
        # Create comparison
        payload = {
            "document_ids": [str(doc1.id), str(doc2.id)],
        }
        
        response = await async_client.post(
            "/api/v1/comparisons",
            json=payload,
            headers=auth_headers,
        )
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["status"] == "queued"
        assert data["owner_id"] == str(test_user.id)
        
        # Verify database records
        job_id = uuid.UUID(data["id"])
        result = await db_session.execute(
            select(ComparisonJob).where(ComparisonJob.id == job_id)
        )
        job = result.scalar_one()
        assert job.status == "queued"
        
        # Verify document associations
        assoc_result = await db_session.execute(
            select(ComparisonJobDocument).where(
                ComparisonJobDocument.comparison_job_id == job_id
            )
        )
        associations = assoc_result.scalars().all()
        assert len(associations) == 2
    
    async def test_create_comparison_validates_minimum_documents(
        self,
        async_client,
        db_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Reject comparison with only 1 document."""
        doc = Document(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            original_filename="single.pdf",
            mime_type="application/pdf",
            file_size_bytes=1000,
            storage_key=f"{test_user.id}/single.pdf",
            file_hash_sha256="x" * 64,
            status="ready",
        )
        db_session.add(doc)
        await db_session.commit()
        
        payload = {"document_ids": [str(doc.id)]}
        
        response = await async_client.post(
            "/api/v1/comparisons",
            json=payload,
            headers=auth_headers,
        )
        
        assert response.status_code == 400
        assert "at least 2 documents" in response.json()["detail"]
    
    async def test_create_comparison_validates_maximum_documents(
        self,
        async_client,
        db_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Reject comparison with more than 5 documents."""
        docs = []
        for i in range(6):
            doc = Document(
                id=uuid.uuid4(),
                owner_id=test_user.id,
                original_filename=f"doc{i}.pdf",
                mime_type="application/pdf",
                file_size_bytes=1000,
                storage_key=f"{test_user.id}/doc{i}.pdf",
                file_hash_sha256=f"{i}" * 64,
                status="ready",
            )
            docs.append(doc)
            db_session.add(doc)
        await db_session.commit()
        
        payload = {"document_ids": [str(d.id) for d in docs]}
        
        response = await async_client.post(
            "/api/v1/comparisons",
            json=payload,
            headers=auth_headers,
        )
        
        assert response.status_code == 400
        assert "maximum 5 documents" in response.json()["detail"]
    
    async def test_create_comparison_validates_ownership(
        self,
        async_client,
        db_session: AsyncSession,
        test_user: User,
        another_user: User,
        auth_headers: dict,
    ):
        """Reject if user doesn't own all documents."""
        doc1 = Document(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            original_filename="mine.pdf",
            mime_type="application/pdf",
            file_size_bytes=1000,
            storage_key=f"{test_user.id}/mine.pdf",
            file_hash_sha256="a" * 64,
            status="ready",
        )
        doc2 = Document(
            id=uuid.uuid4(),
            owner_id=another_user.id,  # Different owner
            original_filename="theirs.pdf",
            mime_type="application/pdf",
            file_size_bytes=1000,
            storage_key=f"{another_user.id}/theirs.pdf",
            file_hash_sha256="b" * 64,
            status="ready",
        )
        db_session.add(doc1)
        db_session.add(doc2)
        await db_session.commit()
        
        payload = {"document_ids": [str(doc1.id), str(doc2.id)]}
        
        response = await async_client.post(
            "/api/v1/comparisons",
            json=payload,
            headers=auth_headers,
        )
        
        assert response.status_code == 400
        assert "not owned by user" in response.json()["detail"]
    
    async def test_create_comparison_validates_document_status(
        self,
        async_client,
        db_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """Reject if documents not ready."""
        doc1 = Document(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            original_filename="ready.pdf",
            mime_type="application/pdf",
            file_size_bytes=1000,
            storage_key=f"{test_user.id}/ready.pdf",
            file_hash_sha256="a" * 64,
            status="ready",
        )
        doc2 = Document(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            original_filename="processing.pdf",
            mime_type="application/pdf",
            file_size_bytes=1000,
            storage_key=f"{test_user.id}/processing.pdf",
            file_hash_sha256="b" * 64,
            status="processing",  # Not ready
        )
        db_session.add(doc1)
        db_session.add(doc2)
        await db_session.commit()
        
        payload = {"document_ids": [str(doc1.id), str(doc2.id)]}
        
        response = await async_client.post(
            "/api/v1/comparisons",
            json=payload,
            headers=auth_headers,
        )
        
        assert response.status_code == 400
        assert "must be 'ready'" in response.json()["detail"]
    
    async def test_get_comparison_success(
        self,
        async_client,
        db_session: AsyncSession,
        test_user: User,
        auth_headers: dict,
    ):
        """GET /comparisons/:id returns comparison job details."""
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
            clause_type="indemnification",
            excerpts_by_document={"doc1": "Excerpt 1", "doc2": "Excerpt 2"},
            diff_summary="Document 2 has broader indemnification",
            materiality="significant",
        )
        db_session.add(result)
        await db_session.commit()
        
        # Get comparison
        response = await async_client.get(
            f"/api/v1/comparisons/{job.id}",
            headers=auth_headers,
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(job.id)
        assert data["status"] == "completed"
        assert len(data["results"]) == 1
        assert data["results"][0]["clause_type"] == "indemnification"
        assert data["results"][0]["materiality"] == "significant"
    
    async def test_get_comparison_not_found(
        self,
        async_client,
        auth_headers: dict,
    ):
        """GET /comparisons/:id returns 404 for nonexistent job."""
        fake_id = uuid.uuid4()
        response = await async_client.get(
            f"/api/v1/comparisons/{fake_id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 404
    
    async def test_get_comparison_enforces_ownership(
        self,
        async_client,
        db_session: AsyncSession,
        test_user: User,
        another_user: User,
        other_auth_headers: dict,
    ):
        """User cannot access another user's comparison."""
        # Create job owned by test_user
        job = ComparisonJob(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            status="completed",
        )
        db_session.add(job)
        await db_session.commit()
        
        # Try to access with another_user
        response = await async_client.get(
            f"/api/v1/comparisons/{job.id}",
            headers=other_auth_headers,
        )
        
        assert response.status_code == 404  # Not found (ownership filtered)


@pytest.mark.asyncio
class TestComparisonWorkerIntegration:
    """Test comparison worker with real database."""

    @patch("app.services.comparison.AsyncAnthropic")
    async def test_run_comparison_full_flow(
        self,
        mock_anthropic_class,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Full comparison flow: create job → run comparison → verify results."""
        # Create 2 documents with clauses
        doc1 = Document(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            original_filename="doc1.pdf",
            mime_type="application/pdf",
            file_size_bytes=1000,
            storage_key=f"{test_user.id}/doc1.pdf",
            file_hash_sha256="a" * 64,
            status="ready",
        )
        doc2 = Document(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            original_filename="doc2.pdf",
            mime_type="application/pdf",
            file_size_bytes=1000,
            storage_key=f"{test_user.id}/doc2.pdf",
            file_hash_sha256="b" * 64,
            status="ready",
        )
        db_session.add(doc1)
        db_session.add(doc2)
        await db_session.commit()
        
        # Add clauses (same type in both documents)
        clause1 = Clause(
            id=uuid.uuid4(),
            document_id=doc1.id,
            clause_type="payment_terms",
            text_excerpt="Net 30 payment terms in doc1",
            risk_level="low",
            risk_rationale="Standard terms",
        )
        clause2 = Clause(
            id=uuid.uuid4(),
            document_id=doc2.id,
            clause_type="payment_terms",
            text_excerpt="Net 60 payment terms in doc2",
            risk_level="medium",
            risk_rationale="Longer payment window",
        )
        db_session.add(clause1)
        db_session.add(clause2)
        await db_session.commit()
        
        # Create comparison job
        job = ComparisonJob(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            status="queued",
        )
        db_session.add(job)
        await db_session.flush()
        
        job_doc1 = ComparisonJobDocument(
            comparison_job_id=job.id,
            document_id=doc1.id,
            document_order=0,
        )
        job_doc2 = ComparisonJobDocument(
            comparison_job_id=job.id,
            document_id=doc2.id,
            document_order=1,
        )
        db_session.add(job_doc1)
        db_session.add(job_doc2)
        await db_session.commit()
        
        # Mock LLM response
        import json
        mock_message = MagicMock()
        mock_message.content = [
            MagicMock(text=json.dumps({
                "clause_type": "payment_terms",
                "diff_summary": "Document 2 allows 30 extra days for payment",
                "materiality": "minor",
            }))
        ]
        
        mock_client = AsyncMock()
        mock_client.messages.create.return_value = mock_message
        mock_anthropic_class.return_value = mock_client
        
        # Run comparison
        from app.services.comparison import run_comparison
        result = await run_comparison(db=db_session, comparison_job_id=job.id)
        
        # Verify results
        assert result["results_count"] == 1
        
        # Check database records
        await db_session.refresh(job)
        assert job.status == "completed"
        assert job.completed_at is not None
        
        # Check comparison result
        results_query = await db_session.execute(
            select(ComparisonResult).where(
                ComparisonResult.comparison_job_id == job.id
            )
        )
        results = results_query.scalars().all()
        assert len(results) == 1
        assert results[0].clause_type == "payment_terms"
        assert results[0].materiality == "minor"
        assert "30 extra days" in results[0].diff_summary
    
    @patch("app.services.comparison.AsyncAnthropic")
    async def test_comparison_with_multiple_clause_types(
        self,
        mock_anthropic_class,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Compare documents with multiple clause types."""
        # Create 2 documents
        doc1 = Document(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            original_filename="doc1.pdf",
            mime_type="application/pdf",
            file_size_bytes=1000,
            storage_key=f"{test_user.id}/doc1.pdf",
            file_hash_sha256="a" * 64,
            status="ready",
        )
        doc2 = Document(
            id=uuid.uuid4(),
            owner_id=test_user.id,
            original_filename="doc2.pdf",
            mime_type="application/pdf",
            file_size_bytes=1000,
            storage_key=f"{test_user.id}/doc2.pdf",
            file_hash_sha256="b" * 64,
            status="ready",
        )
        db_session.add(doc1)
        db_session.add(doc2)
        await db_session.commit()
        
        # Add multiple clause types
        clauses = [
            Clause(id=uuid.uuid4(), document_id=doc1.id, clause_type="termination", text_excerpt="Term1", risk_level="low"),
            Clause(id=uuid.uuid4(), document_id=doc2.id, clause_type="termination", text_excerpt="Term2", risk_level="low"),
            Clause(id=uuid.uuid4(), document_id=doc1.id, clause_type="liability", text_excerpt="Liab1", risk_level="high"),
            Clause(id=uuid.uuid4(), document_id=doc2.id, clause_type="liability", text_excerpt="Liab2", risk_level="high"),
        ]
        for clause in clauses:
            db_session.add(clause)
        await db_session.commit()
        
        # Create job
        job = ComparisonJob(id=uuid.uuid4(), owner_id=test_user.id, status="queued")
        db_session.add(job)
        await db_session.flush()
        
        db_session.add(ComparisonJobDocument(comparison_job_id=job.id, document_id=doc1.id, document_order=0))
        db_session.add(ComparisonJobDocument(comparison_job_id=job.id, document_id=doc2.id, document_order=1))
        await db_session.commit()
        
        # Mock LLM responses (2 clause types)
        import json
        mock_client = AsyncMock()
        mock_client.messages.create.side_effect = [
            MagicMock(content=[MagicMock(text=json.dumps({
                "clause_type": "termination",
                "diff_summary": "Different notice periods",
                "materiality": "minor",
            }))]),
            MagicMock(content=[MagicMock(text=json.dumps({
                "clause_type": "liability",
                "diff_summary": "Document 2 has unlimited liability",
                "materiality": "critical",
            }))]),
        ]
        mock_anthropic_class.return_value = mock_client
        
        # Run comparison
        from app.services.comparison import run_comparison
        result = await run_comparison(db=db_session, comparison_job_id=job.id)
        
        # Verify 2 results created
        assert result["results_count"] == 2
        
        results_query = await db_session.execute(
            select(ComparisonResult).where(
                ComparisonResult.comparison_job_id == job.id
            )
        )
        results = results_query.scalars().all()
        assert len(results) == 2
        
        clause_types = {r.clause_type for r in results}
        assert clause_types == {"termination", "liability"}
