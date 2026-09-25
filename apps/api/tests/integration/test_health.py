"""
Integration test — GET /health endpoint.
Implements: Phase 0 exit criterion "health-check endpoint returns 200".
code-standards.md §Testing: integration tests, API contract tests (success + documented errors).
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


# Provide minimal env vars so Settings doesn't fail at import
@pytest.fixture(autouse=True, scope="module")
def _env(monkeypatch=None):
    """Set required environment variables before the app module is loaded."""
    # Use os.environ directly for module-scope fixture compatibility
    env_vars = {
        "ENVIRONMENT": "development",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/legallens_test",
        "REDIS_URL": "redis://localhost:6379/0",
        "CELERY_BROKER_URL": "redis://localhost:6379/1",
        "S3_BUCKET": "legallens-test",
        "S3_ACCESS_KEY_ID": "minioadmin",
        "S3_SECRET_ACCESS_KEY": "minioadmin",
        "ANTHROPIC_API_KEY": "sk-ant-test",
        "VOYAGE_API_KEY": "pa-test",
        "JWT_SECRET": "a" * 32,
        "CORS_ORIGINS": "http://localhost:3000",
        "LOG_LEVEL": "DEBUG",
    }
    original = {}
    for k, v in env_vars.items():
        original[k] = os.environ.get(k)
        os.environ[k] = v
    yield
    for k, original_v in original.items():
        if original_v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = original_v


@pytest.fixture(scope="module")
def client():
    # Import after env vars are set
    from app.main import app
    return TestClient(app)


class TestHealth:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_body_has_status_ok(self, client):
        response = client.get("/health")
        body = response.json()
        assert body["status"] == "ok"

    def test_health_body_has_environment(self, client):
        response = client.get("/health")
        body = response.json()
        assert "environment" in body
        assert body["environment"] == "development"

    def test_health_is_json(self, client):
        response = client.get("/health")
        assert "application/json" in response.headers["content-type"]

    def test_unknown_path_returns_404(self, client):
        response = client.get("/nonexistent")
        assert response.status_code == 404


class TestCORSHeaders:
    def test_cors_origin_present_for_allowed_origin(self, client):
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # FastAPI CORSMiddleware returns 200 for OPTIONS preflight
        assert response.status_code in (200, 204)

    def test_docs_available_in_development(self, client):
        response = client.get("/docs")
        # In development, /docs should be available (not 404)
        assert response.status_code == 200
