"""
Integration tests — document endpoints
Tests: POST /documents, GET /documents/{id}, DELETE /documents/{id}.
Covers: architecture.md §8 API contracts, code-standards.md §Authorization.
"""

import io
from unittest.mock import patch, AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.models.user import User
from app.models.document import Document


class TestUploadDocument:
    """Test POST /api/v1/documents"""

    @patch("app.services.ingestion.upload_to_s3", new_callable=AsyncMock)
    @patch("app.services.ingestion.record_audit_event", new_callable=AsyncMock)
    def test_upload_succeeds_with_valid_pdf(
        self,
        mock_audit,
        mock_s3,
        test_client: TestClient,
        auth_headers: dict,
    ):
        pdf_content = b"%PDF-1.4\nTest PDF content"
        files = {"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")}
        
        response = test_client.post(
            "/api/v1/documents",
            files=files,
            headers=auth_headers,
        )
        
        assert response.status_code == 202
        data = response.json()
        assert "id" in data
        assert data["status"] == "uploaded"
        assert data["mime_type"] == "application/pdf"
        assert data["original_filename"] == "test.pdf"
        
        # Verify S3 upload was called
        mock_s3.assert_awaited_once()
        mock_audit.assert_awaited_once()

    def test_upload_requires_authentication(self, test_client: TestClient):
        pdf_content = b"%PDF-1.4\nTest"
        files = {"file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")}
        
        response = test_client.post("/api/v1/documents", files=files)
        
        assert response.status_code == 401

    @patch("app.services.ingestion.upload_to_s3", new_callable=AsyncMock)
    @patch("app.services.ingestion.record_audit_event", new_callable=AsyncMock)
    def test_upload_rejects_unsupported_file_type(
        self,
        mock_audit,
        mock_s3,
        test_client: TestClient,
        auth_headers: dict,
    ):
        # JPEG magic bytes
        jpeg_content = b"\xff\xd8\xff\xe0\x00\x10JFIF"
        files = {"file": ("photo.jpg", io.BytesIO(jpeg_content), "image/jpeg")}
        
        response = test_client.post(
            "/api/v1/documents",
            files=files,
            headers=auth_headers,
        )
        
        assert response.status_code == 400
        assert "unsupported" in response.json()["detail"].lower()


class TestGetDocument:
    """Test GET /api/v1/documents/{id}"""

    def test_get_document_succeeds_for_owner(
        self,
        test_client: TestClient,
        auth_headers: dict,
        test_document: Document,
    ):
        response = test_client.get(
            f"/api/v1/documents/{test_document.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_document.id)
        assert data["original_filename"] == test_document.original_filename
        assert data["status"] == test_document.status

    def test_get_document_returns_404_for_other_user(
        self,
        test_client: TestClient,
        other_auth_headers: dict,
        test_document: Document,
    ):
        # code-standards.md: Returns 404 (not 403) to avoid confirming existence
        response = test_client.get(
            f"/api/v1/documents/{test_document.id}",
            headers=other_auth_headers,
        )
        
        assert response.status_code == 404

    def test_get_document_requires_authentication(
        self,
        test_client: TestClient,
        test_document: Document,
    ):
        response = test_client.get(f"/api/v1/documents/{test_document.id}")
        
        assert response.status_code == 401

    def test_get_document_returns_404_for_nonexistent(
        self,
        test_client: TestClient,
        auth_headers: dict,
    ):
        import uuid
        fake_id = uuid.uuid4()
        response = test_client.get(
            f"/api/v1/documents/{fake_id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 404


class TestGetDocumentStatus:
    """Test GET /api/v1/documents/{id}/status"""

    def test_get_status_succeeds_for_owner(
        self,
        test_client: TestClient,
        auth_headers: dict,
        test_document: Document,
    ):
        response = test_client.get(
            f"/api/v1/documents/{test_document.id}/status",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == test_document.status
        assert "processing_stage" in data

    def test_get_status_enforces_ownership(
        self,
        test_client: TestClient,
        other_auth_headers: dict,
        test_document: Document,
    ):
        response = test_client.get(
            f"/api/v1/documents/{test_document.id}/status",
            headers=other_auth_headers,
        )
        
        assert response.status_code == 404


class TestDeleteDocument:
    """Test DELETE /api/v1/documents/{id}"""

    @patch("app.services.storage.delete_from_s3", new_callable=AsyncMock)
    @patch("app.services.audit.record_audit_event", new_callable=AsyncMock)
    def test_delete_document_succeeds_for_owner(
        self,
        mock_audit,
        mock_s3,
        test_client: TestClient,
        auth_headers: dict,
        test_document: Document,
    ):
        response = test_client.delete(
            f"/api/v1/documents/{test_document.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 204
        
        # Verify S3 delete was called
        mock_s3.assert_awaited_once()
        mock_audit.assert_awaited_once()
        
        # Verify document is gone
        get_response = test_client.get(
            f"/api/v1/documents/{test_document.id}",
            headers=auth_headers,
        )
        assert get_response.status_code == 404

    def test_delete_document_enforces_ownership(
        self,
        test_client: TestClient,
        other_auth_headers: dict,
        test_document: Document,
    ):
        # code-standards.md §Authorization: ownership check is not optional
        response = test_client.delete(
            f"/api/v1/documents/{test_document.id}",
            headers=other_auth_headers,
        )
        
        assert response.status_code == 404

    def test_delete_document_requires_authentication(
        self,
        test_client: TestClient,
        test_document: Document,
    ):
        response = test_client.delete(f"/api/v1/documents/{test_document.id}")
        
        assert response.status_code == 401

    def test_delete_document_returns_404_for_nonexistent(
        self,
        test_client: TestClient,
        auth_headers: dict,
    ):
        import uuid
        fake_id = uuid.uuid4()
        response = test_client.delete(
            f"/api/v1/documents/{fake_id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 404
