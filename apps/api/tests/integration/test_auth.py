"""
Integration tests — /api/v1/auth endpoints
Implements: code-standards.md §Testing Integration — "API contract tests for every
  endpoint (success + documented error responses)"
  and "ownership/authorization tests — a second user's token must get 403/404 on
  every resource-scoped endpoint."

Uses: in-memory SQLite (aiosqlite) + FastAPI TestClient (httpx)
All external I/O (S3, Celery) patched at the service boundary.

Test matrix:
  POST /auth/register  → 201 success, 409 duplicate email, 400 weak password
  POST /auth/login     → 200 success, 401 wrong password, 401 unknown email
  POST /auth/refresh   → 200 success, 401 expired/invalid refresh token
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

from tests.integration.conftest import app, override_get_db  # noqa: F401 — imported for fixtures


pytestmark = pytest.mark.asyncio


# ── Register ──────────────────────────────────────────────────────────────────

class TestRegister:
    async def test_register_returns_201_with_token_pair(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "alice@example.com",
            "password": "SecurePass1!",
            "full_name": "Alice Example",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert "user" in body
        assert body["user"]["email"] == "alice@example.com"
        assert "password_hash" not in body["user"]  # must never be exposed
        assert "tokens" in body
        assert body["tokens"]["token_type"] == "bearer"
        assert body["tokens"]["access_token"]
        assert body["tokens"]["refresh_token"]

    async def test_register_duplicate_email_returns_409(self, client: AsyncClient):
        payload = {
            "email": "bob@example.com",
            "password": "SecurePass1!",
            "full_name": "Bob",
        }
        r1 = await client.post("/api/v1/auth/register", json=payload)
        assert r1.status_code == 201
        r2 = await client.post("/api/v1/auth/register", json=payload)
        assert r2.status_code == 409
        assert "already exists" in r2.json()["detail"].lower()

    async def test_register_short_password_returns_422(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "charlie@example.com",
            "password": "short",  # < 8 chars
            "full_name": "Charlie",
        })
        assert resp.status_code == 422

    async def test_register_trivial_password_returns_422(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "dave@example.com",
            "password": "password",  # in trivial list
            "full_name": "Dave",
        })
        assert resp.status_code == 422

    async def test_register_invalid_email_returns_422(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "not-an-email",
            "password": "SecurePass1!",
            "full_name": "Eve",
        })
        assert resp.status_code == 422

    async def test_register_missing_full_name_returns_422(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "frank@example.com",
            "password": "SecurePass1!",
        })
        assert resp.status_code == 422


# ── Login ─────────────────────────────────────────────────────────────────────

class TestLogin:
    async def test_login_success_returns_token_pair(self, registered_user, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login", json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["token_type"] == "bearer"

    async def test_login_wrong_password_returns_401(self, registered_user, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login", json={
            "email": registered_user["email"],
            "password": "wrong_password_!",
        })
        assert resp.status_code == 401
        # Must not distinguish between wrong email and wrong password
        assert "Invalid" in resp.json()["detail"]

    async def test_login_unknown_email_returns_401(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "nobody@example.com",
            "password": "SecurePass1!",
        })
        assert resp.status_code == 401

    async def test_login_empty_password_returns_422(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/login", json={
            "email": "nobody@example.com",
            "password": "",
        })
        assert resp.status_code == 422


# ── Refresh ───────────────────────────────────────────────────────────────────

class TestRefresh:
    async def test_refresh_returns_new_token_pair(self, registered_user, client: AsyncClient):
        # Login to get a refresh token
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        })
        refresh_token = login_resp.json()["refresh_token"]

        resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"]
        assert body["refresh_token"]

    async def test_refresh_invalid_token_returns_401(self, client: AsyncClient):
        resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": "not.a.valid.token",
        })
        assert resp.status_code == 401

    async def test_access_token_rejected_as_refresh(self, registered_user, client: AsyncClient):
        """An access token must not be accepted as a refresh token."""
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        })
        access_token = login_resp.json()["access_token"]

        resp = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": access_token,  # wrong kind
        })
        assert resp.status_code == 401
