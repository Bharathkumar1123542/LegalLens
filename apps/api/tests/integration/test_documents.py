"""
Integration tests — /api/v1/documents endpoints
code-standards.md §Testing Integration:
  "API contract tests for every endpoint (success + documented error responses)"
  "ownership/authorization tests — a second user's token must get 403/404 on
   every resource-scoped endpoint."

Test matrix:
  POST   /documents              → 202, 400 (bad type), 413 (too large), 401 (no token)
  GET    /documents/{id}         → 200, 404 (not found), 404 (wrong user — not 403)
  GET    /documents/{id}/status  → 200, 404
  DELETE /documents/{id}         → 204, 404 (wrong user)
  Deduplication                  → returns existing doc on same hash+owner
"""

from __future__ import annotations

import io
import uuid

import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock

pytestmark = pytest.mark.asyncio

PDF_BYTES = b"%PDF-1.4 fake pdf bytes for test"
DOCX_BYTES = b"\x50\x4B\x03\x04" + b"\x00" * 64  # DOCX magic + padding
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 64  # unsupported type


def _pdf_file(content: bytes = PDF_BYTES, name: str = "contract.pdf"):
    return ("file", (name, io.BytesIO(content), "application/pdf"))


class TestUploadDocument:
    async def test_upload_valid_pdf_returns_202(self, auth_client: AsyncClient):
        with patch("app.services.ingestion.upload_to_s3", new_callable=AsyncMock):
            resp = await auth_client.post("/api/v1/documents", files=[_pdf_file()])
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "uploaded"
        assert body["original_filename"] == "contract.pdf"
        assert "id" in body

    async def test_upload_unsupported_type_returns_400(self, auth_client: AsyncClient):
        with patch("app.services.ingestion.upload_to_s3", new_callable=AsyncMock):
            resp = await auth_client.post(
                "/api/v1/documents",
                files=[("file", ("photo.jpg", io.BytesIO(JPEG_BYTES), "image/jpeg"))],
            )
        assert resp.status_code == 400
        assert "Unsupported file type" in resp.json()["detail"]

    async def test_upload_empty_file_returns_400(self, auth_client: AsyncClient):
        with patch("app.services.ingestion.upload_to_s3", new_callable=AsyncMock):
            resp = await auth_client.post(
                "/api/v1/documents",
                files=[("file", ("empty.pdf", io.BytesIO(b""), "application/pdf"))],
            )
        assert resp.status_code == 400

    async def test_upload_without_auth_returns_401(self, client: AsyncClient):
        resp = await client.post("/api/v1/documents", files=[_pdf_file()])
        assert resp.status_code == 401

    async def test_upload_deduplication_returns_same_id(self, auth_client: AsyncClient):
        """Uploading the same file twice returns the existing document ID."""
        with patch("app.services.ingestion.upload_to_s3", new_callable=AsyncMock):
            r1 = await auth_client.post("/api/v1/documents", files=[_pdf_file()])
            r2 = await auth_client.post("/api/v1/documents", files=[_pdf_file()])
        assert r1.status_code == 202
        assert r2.status_code == 202
        assert r1.json()["id"] == r2.json()["id"]


class TestGetDocument:
    async def test_get_own_document_returns_200(self, auth_client: AsyncClient):
        with patch("app.services.ingestion.upload_to_s3", new_callable=AsyncMock):
            upload_resp = await auth_client.post("/api/v1/documents", files=[_pdf_file()])
        doc_id = upload_resp.json()["id"]

        resp = await auth_client.get(f"/api/v1/documents/{doc_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == doc_id
        assert body["status"] == "uploaded"
        assert "password_hash" not in body  # sanity: no user PII bleed

    async def test_get_nonexistent_document_returns_404(self, auth_client: AsyncClient):
        resp = await auth_client.get(f"/api/v1/documents/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_get_other_users_document_returns_404(
        self, auth_client: AsyncClient, second_auth_client: AsyncClient
    ):
        """
        code-standards.md §Authorization: a second user's token must get 404 (not 403)
        to avoid confirming the document's existence to an unauthorised caller.
        """
        with patch("app.services.ingestion.upload_to_s3", new_callable=AsyncMock):
            upload_resp = await auth_client.post("/api/v1/documents", files=[_pdf_file()])
        doc_id = upload_resp.json()["id"]

        resp = await second_auth_client.get(f"/api/v1/documents/{doc_id}")
        assert resp.status_code == 404

    async def test_get_without_auth_returns_401(self, client: AsyncClient):
        resp = await client.get(f"/api/v1/documents/{uuid.uuid4()}")
        assert resp.status_code == 401


class TestDocumentStatus:
    async def test_status_returns_200_with_status_field(self, auth_client: AsyncClient):
        with patch("app.services.ingestion.upload_to_s3", new_callable=AsyncMock):
            upload_resp = await auth_client.post("/api/v1/documents", files=[_pdf_file()])
        doc_id = upload_resp.json()["id"]

        resp = await auth_client.get(f"/api/v1/documents/{doc_id}/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "uploaded"
        assert body["id"] == doc_id

    async def test_status_other_user_returns_404(
        self, auth_client: AsyncClient, second_auth_client: AsyncClient
    ):
        with patch("app.services.ingestion.upload_to_s3", new_callable=AsyncMock):
            upload_resp = await auth_client.post("/api/v1/documents", files=[_pdf_file()])
        doc_id = upload_resp.json()["id"]

        resp = await second_auth_client.get(f"/api/v1/documents/{doc_id}/status")
        assert resp.status_code == 404


class TestDeleteDocument:
    async def test_delete_own_document_returns_204(self, auth_client: AsyncClient):
        with patch("app.services.ingestion.upload_to_s3", new_callable=AsyncMock):
            upload_resp = await auth_client.post("/api/v1/documents", files=[_pdf_file()])
        doc_id = upload_resp.json()["id"]

        with patch("app.services.documents.delete_from_s3", new_callable=AsyncMock):
            with patch("app.api.v1.documents.delete_from_s3", new_callable=AsyncMock):
                resp = await auth_client.delete(f"/api/v1/documents/{doc_id}")
        assert resp.status_code == 204

        # Verify document is gone
        get_resp = await auth_client.get(f"/api/v1/documents/{doc_id}")
        assert get_resp.status_code == 404

    async def test_delete_other_users_document_returns_404(
        self, auth_client: AsyncClient, second_auth_client: AsyncClient
    ):
        with patch("app.services.ingestion.upload_to_s3", new_callable=AsyncMock):
            upload_resp = await auth_client.post("/api/v1/documents", files=[_pdf_file()])
        doc_id = upload_resp.json()["id"]

        with patch("app.api.v1.documents.delete_from_s3", new_callable=AsyncMock):
            resp = await second_auth_client.delete(f"/api/v1/documents/{doc_id}")
        assert resp.status_code == 404

    async def test_delete_without_auth_returns_401(self, client: AsyncClient):
        resp = await client.delete(f"/api/v1/documents/{uuid.uuid4()}")
        assert resp.status_code == 401
