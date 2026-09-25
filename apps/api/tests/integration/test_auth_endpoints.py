"""
Integration tests — auth endpoints
Tests: POST /auth/register, POST /auth/login, POST /auth/refresh.
Covers: architecture.md §8 API contracts, code-standards.md §Security.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class TestRegister:
    """Test POST /api/v1/auth/register"""

    def test_register_creates_user_and_returns_tokens(self, test_client: TestClient):
        response = test_client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "SecurePassword123!",
                "full_name": "New User",
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "user" in data
        assert data["user"]["email"] == "newuser@example.com"
        assert data["user"]["full_name"] == "New User"
        assert data["user"]["role"] == "user"
        assert "tokens" in data
        assert "access_token" in data["tokens"]
        assert "refresh_token" in data["tokens"]

    def test_register_rejects_duplicate_email(self, test_client: TestClient, test_user: User):
        response = test_client.post(
            "/api/v1/auth/register",
            json={
                "email": test_user.email,
                "password": "AnyPassword123!",
                "full_name": "Duplicate",
            },
        )
        
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    def test_register_rejects_invalid_email(self, test_client: TestClient):
        response = test_client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "Password123!",
                "full_name": "Test",
            },
        )
        
        assert response.status_code == 422  # Pydantic validation error

    def test_register_rejects_missing_fields(self, test_client: TestClient):
        response = test_client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com"},
        )
        
        assert response.status_code == 422


class TestLogin:
    """Test POST /api/v1/auth/login"""

    def test_login_succeeds_with_correct_credentials(self, test_client: TestClient, test_user: User):
        response = test_client.post(
            "/api/v1/auth/login",
            json={
                "email": "testuser@example.com",
                "password": "TestPassword123!",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert "expires_in" in data

    def test_login_rejects_wrong_password(self, test_client: TestClient, test_user: User):
        response = test_client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "WrongPassword",
            },
        )
        
        assert response.status_code == 401
        # Must not distinguish email vs password (user enumeration prevention)
        assert "invalid email or password" in response.json()["detail"].lower()

    def test_login_rejects_nonexistent_user(self, test_client: TestClient):
        response = test_client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "AnyPassword",
            },
        )
        
        assert response.status_code == 401

    def test_login_rejects_inactive_user(self, test_client: TestClient, db_session: AsyncSession, test_user: User):
        # Deactivate the user
        test_user.is_active = False
        db_session.add(test_user)
        # Must use sync commit for TestClient
        import asyncio
        asyncio.run(db_session.commit())
        
        response = test_client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "TestPassword123!",
            },
        )
        
        assert response.status_code == 403
        assert "deactivated" in response.json()["detail"].lower()


class TestRefresh:
    """Test POST /api/v1/auth/refresh"""

    def test_refresh_succeeds_with_valid_token(self, test_client: TestClient, test_user: User):
        # First login to get a refresh token
        login_response = test_client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "TestPassword123!",
            },
        )
        refresh_token = login_response.json()["refresh_token"]
        
        # Use the refresh token
        response = test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_rejects_invalid_token(self, test_client: TestClient):
        response = test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.jwt.token"},
        )
        
        assert response.status_code == 401

    def test_refresh_rejects_access_token(self, test_client: TestClient, test_user: User):
        # Login to get an access token
        login_response = test_client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "TestPassword123!",
            },
        )
        access_token = login_response.json()["access_token"]
        
        # Try to use access token as refresh token (should fail)
        response = test_client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},
        )
        
        assert response.status_code == 401
        assert "not a refresh token" in response.json()["detail"].lower()
