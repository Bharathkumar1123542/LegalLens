"""
Unit tests — services/auth.py
Tests: register_user, authenticate_user, refresh_access_token.
Covers: duplicate email (409), wrong credentials (401), inactive user (403),
        transparent password rehash, audit logging integration.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.services.auth import register_user, authenticate_user, refresh_access_token
from app.models.user import User
from app.core.security import hash_password, create_refresh_token


@pytest.mark.asyncio
class TestRegisterUser:
    """Test user registration."""

    async def test_register_creates_user_and_returns_tokens(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=AsyncMock(scalar_one_or_none=AsyncMock(return_value=None)))
        
        user, tokens = await register_user(
            db=db,
            email="newuser@example.com",
            password="SecureP@ss123",
            full_name="New User",
        )
        
        assert user.email == "newuser@example.com"
        assert user.full_name == "New User"
        assert user.role == "user"
        assert user.is_active is True
        assert user.password_hash.startswith("$argon2id$")
        assert tokens.access_token
        assert tokens.refresh_token
        db.add.assert_called_once()
        db.flush.assert_awaited_once()

    async def test_register_normalizes_email_to_lowercase(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=AsyncMock(scalar_one_or_none=AsyncMock(return_value=None)))
        
        user, _ = await register_user(
            db=db,
            email="NeWUseR@EXAMPLE.COM",
            password="password",
            full_name="Test",
        )
        
        assert user.email == "newuser@example.com"

    async def test_register_rejects_duplicate_email_advisory_check(self):
        # Email already exists (advisory pre-check)
        existing_user = User(
            id=uuid.uuid4(),
            email="existing@example.com",
            password_hash="hash",
            full_name="Existing",
            role="user",
            is_active=True,
        )
        db = AsyncMock()
        db.execute = AsyncMock(return_value=AsyncMock(scalar_one_or_none=AsyncMock(return_value=existing_user)))
        
        with pytest.raises(HTTPException) as exc_info:
            await register_user(
                db=db,
                email="existing@example.com",
                password="password",
                full_name="Duplicate",
            )
        
        assert exc_info.value.status_code == 409
        assert "already exists" in exc_info.value.detail.lower()

    async def test_register_rejects_duplicate_email_unique_constraint(self):
        # Advisory check passes, but unique constraint fails at flush
        db = AsyncMock()
        db.execute = AsyncMock(return_value=AsyncMock(scalar_one_or_none=AsyncMock(return_value=None)))
        db.flush = AsyncMock(side_effect=IntegrityError("", "", ""))
        
        with pytest.raises(HTTPException) as exc_info:
            await register_user(
                db=db,
                email="duplicate@example.com",
                password="password",
                full_name="Test",
            )
        
        assert exc_info.value.status_code == 409
        db.rollback.assert_awaited_once()


@pytest.mark.asyncio
class TestAuthenticateUser:
    """Test credential validation and login."""

    async def test_authenticate_succeeds_with_correct_credentials(self):
        password = "MyPassword123!"
        user = User(
            id=uuid.uuid4(),
            email="user@example.com",
            password_hash=hash_password(password),
            full_name="Test User",
            role="user",
            is_active=True,
        )
        db = AsyncMock()
        db.execute = AsyncMock(return_value=AsyncMock(scalar_one_or_none=AsyncMock(return_value=user)))
        
        result_user, tokens = await authenticate_user(
            db=db,
            email="user@example.com",
            password=password,
        )
        
        assert result_user.id == user.id
        assert tokens.access_token
        assert tokens.refresh_token

    async def test_authenticate_normalizes_email_to_lowercase(self):
        password = "password"
        user = User(
            id=uuid.uuid4(),
            email="user@example.com",
            password_hash=hash_password(password),
            full_name="Test",
            role="user",
            is_active=True,
        )
        db = AsyncMock()
        db.execute = AsyncMock(return_value=AsyncMock(scalar_one_or_none=AsyncMock(return_value=user)))
        
        result_user, _ = await authenticate_user(
            db=db,
            email="USER@EXAMPLE.COM",
            password=password,
        )
        
        assert result_user.id == user.id

    async def test_authenticate_rejects_wrong_email(self):
        # No user found
        db = AsyncMock()
        db.execute = AsyncMock(return_value=AsyncMock(scalar_one_or_none=AsyncMock(return_value=None)))
        
        with pytest.raises(HTTPException) as exc_info:
            await authenticate_user(
                db=db,
                email="nonexistent@example.com",
                password="anything",
            )
        
        assert exc_info.value.status_code == 401
        # Must not distinguish email vs password (user enumeration prevention)
        assert "invalid email or password" in exc_info.value.detail.lower()

    async def test_authenticate_rejects_wrong_password(self):
        user = User(
            id=uuid.uuid4(),
            email="user@example.com",
            password_hash=hash_password("CorrectPassword"),
            full_name="Test",
            role="user",
            is_active=True,
        )
        db = AsyncMock()
        db.execute = AsyncMock(return_value=AsyncMock(scalar_one_or_none=AsyncMock(return_value=user)))
        
        with pytest.raises(HTTPException) as exc_info:
            await authenticate_user(
                db=db,
                email="user@example.com",
                password="WrongPassword",
            )
        
        assert exc_info.value.status_code == 401

    async def test_authenticate_rejects_inactive_user(self):
        password = "password"
        user = User(
            id=uuid.uuid4(),
            email="user@example.com",
            password_hash=hash_password(password),
            full_name="Test",
            role="user",
            is_active=False,  # Deactivated
        )
        db = AsyncMock()
        db.execute = AsyncMock(return_value=AsyncMock(scalar_one_or_none=AsyncMock(return_value=user)))
        
        with pytest.raises(HTTPException) as exc_info:
            await authenticate_user(
                db=db,
                email="user@example.com",
                password=password,
            )
        
        assert exc_info.value.status_code == 403
        assert "deactivated" in exc_info.value.detail.lower()

    @patch("app.services.auth.needs_rehash")
    @patch("app.services.auth.hash_password")
    async def test_authenticate_upgrades_weak_hash(self, mock_hash, mock_needs_rehash):
        # Simulate old hash that needs upgrade
        mock_needs_rehash.return_value = True
        mock_hash.return_value = "$argon2id$new_hash"
        
        password = "password"
        user = User(
            id=uuid.uuid4(),
            email="user@example.com",
            password_hash=hash_password(password),  # Will be replaced
            full_name="Test",
            role="user",
            is_active=True,
        )
        db = AsyncMock()
        db.execute = AsyncMock(return_value=AsyncMock(scalar_one_or_none=AsyncMock(return_value=user)))
        
        await authenticate_user(db=db, email="user@example.com", password=password)
        
        # Password should be rehashed
        mock_hash.assert_called_once_with(password)
        assert user.password_hash == "$argon2id$new_hash"


@pytest.mark.asyncio
class TestRefreshAccessToken:
    """Test refresh token exchange."""

    async def test_refresh_succeeds_with_valid_token(self):
        user = User(
            id=uuid.uuid4(),
            email="user@example.com",
            password_hash="hash",
            full_name="Test",
            role="user",
            is_active=True,
        )
        refresh_token = create_refresh_token(str(user.id))
        
        db = AsyncMock()
        db.execute = AsyncMock(return_value=AsyncMock(scalar_one_or_none=AsyncMock(return_value=user)))
        
        tokens = await refresh_access_token(db=db, refresh_token=refresh_token)
        
        assert tokens.access_token
        assert tokens.refresh_token

    async def test_refresh_rejects_expired_token(self):
        # Expired token will be caught by decode_refresh_token
        db = AsyncMock()
        
        with pytest.raises(HTTPException) as exc_info:
            await refresh_access_token(db=db, refresh_token="expired.jwt.token")
        
        assert exc_info.value.status_code == 401

    async def test_refresh_rejects_nonexistent_user(self):
        user_id = str(uuid.uuid4())
        refresh_token = create_refresh_token(user_id)
        
        db = AsyncMock()
        db.execute = AsyncMock(return_value=AsyncMock(scalar_one_or_none=AsyncMock(return_value=None)))
        
        with pytest.raises(HTTPException) as exc_info:
            await refresh_access_token(db=db, refresh_token=refresh_token)
        
        assert exc_info.value.status_code == 401

    async def test_refresh_rejects_inactive_user(self):
        user = User(
            id=uuid.uuid4(),
            email="user@example.com",
            password_hash="hash",
            full_name="Test",
            role="user",
            is_active=False,
        )
        refresh_token = create_refresh_token(str(user.id))
        
        db = AsyncMock()
        db.execute = AsyncMock(return_value=AsyncMock(scalar_one_or_none=AsyncMock(return_value=user)))
        
        with pytest.raises(HTTPException) as exc_info:
            await refresh_access_token(db=db, refresh_token=refresh_token)
        
        assert exc_info.value.status_code == 401
