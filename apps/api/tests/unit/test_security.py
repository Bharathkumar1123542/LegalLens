"""
Unit tests — core/security.py (password hashing, JWT)
Tests: architecture.md §4 auth stack, code-standards.md §Security rules.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import jwt as pyjwt

from app.core.security import (
    hash_password,
    verify_password,
    needs_rehash,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    TokenError,
)
from app.core.config import settings


class TestPasswordHashing:
    """Test argon2id hashing and verification."""

    def test_hash_password_returns_valid_argon2id_hash(self):
        plaintext = "SecureP@ssw0rd123"
        hashed = hash_password(plaintext)
        
        assert hashed.startswith("$argon2id$")
        assert len(hashed) > 80  # argon2id hashes are ~90 chars

    def test_verify_password_accepts_correct_plaintext(self):
        plaintext = "MySecret123!"
        hashed = hash_password(plaintext)
        
        assert verify_password(plaintext, hashed) is True

    def test_verify_password_rejects_incorrect_plaintext(self):
        hashed = hash_password("CorrectPassword")
        
        assert verify_password("WrongPassword", hashed) is False

    def test_verify_password_rejects_malformed_hash(self):
        # Not a valid argon2 hash
        assert verify_password("anything", "not-a-hash") is False
        assert verify_password("anything", "") is False

    def test_needs_rehash_with_current_parameters(self):
        # Hash with current params should not need rehash
        hashed = hash_password("test123")
        assert needs_rehash(hashed) is False

    @patch("app.core.security._ph")
    def test_needs_rehash_with_weaker_parameters(self, mock_ph):
        # Simulate a hash made with older/weaker params
        mock_ph.check_needs_rehash.return_value = True
        assert needs_rehash("$argon2id$v=19$m=16384,t=1,p=1$...") is True


class TestJWTCreation:
    """Test JWT access and refresh token creation."""

    def test_create_access_token_has_correct_structure(self):
        user_id = str(uuid.uuid4())
        email = "test@example.com"
        
        token = create_access_token(user_id, email)
        
        # Decode without verification to inspect payload
        payload = pyjwt.decode(
            token,
            options={"verify_signature": False},
        )
        
        assert payload["sub"] == user_id
        assert payload["kind"] == "access"
        assert payload["email"] == email
        assert "jti" in payload
        assert "exp" in payload
        assert "iat" in payload

    def test_create_access_token_expires_in_15_minutes(self):
        user_id = str(uuid.uuid4())
        before = datetime.now(timezone.utc)
        
        token = create_access_token(user_id, "test@example.com")
        
        after = datetime.now(timezone.utc)
        payload = pyjwt.decode(token, options={"verify_signature": False})
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        
        # exp should be ~15 minutes from now
        expected_min = before + timedelta(minutes=15)
        expected_max = after + timedelta(minutes=15)
        assert expected_min <= exp <= expected_max

    def test_create_refresh_token_has_correct_structure(self):
        user_id = str(uuid.uuid4())
        
        token = create_refresh_token(user_id)
        
        payload = pyjwt.decode(token, options={"verify_signature": False})
        
        assert payload["sub"] == user_id
        assert payload["kind"] == "refresh"
        assert "jti" in payload
        assert "email" not in payload  # refresh tokens contain no PII

    def test_create_refresh_token_expires_in_14_days(self):
        user_id = str(uuid.uuid4())
        before = datetime.now(timezone.utc)
        
        token = create_refresh_token(user_id)
        
        after = datetime.now(timezone.utc)
        payload = pyjwt.decode(token, options={"verify_signature": False})
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        
        # exp should be ~14 days from now
        expected_min = before + timedelta(days=14)
        expected_max = after + timedelta(days=14)
        assert expected_min <= exp <= expected_max


class TestJWTDecoding:
    """Test JWT validation and error handling."""

    def test_decode_access_token_succeeds_with_valid_token(self):
        user_id = str(uuid.uuid4())
        token = create_access_token(user_id, "test@example.com")
        
        payload = decode_access_token(token)
        
        assert payload["sub"] == user_id
        assert payload["kind"] == "access"

    def test_decode_access_token_rejects_refresh_token(self):
        user_id = str(uuid.uuid4())
        token = create_refresh_token(user_id)
        
        with pytest.raises(TokenError, match="not an access token"):
            decode_access_token(token)

    def test_decode_access_token_rejects_expired_token(self):
        user_id = str(uuid.uuid4())
        # Create token with immediate expiry
        with patch("app.core.security._ACCESS_EXPIRE", timedelta(seconds=-1)):
            token = create_access_token(user_id, "test@example.com")
        
        with pytest.raises(TokenError, match="expired"):
            decode_access_token(token)

    def test_decode_access_token_rejects_tampered_token(self):
        user_id = str(uuid.uuid4())
        token = create_access_token(user_id, "test@example.com")
        
        # Tamper with the token
        tampered = token[:-10] + "0000000000"
        
        with pytest.raises(TokenError, match="Invalid"):
            decode_access_token(tampered)

    def test_decode_access_token_rejects_wrong_signature(self):
        # Token signed with a different secret
        payload = {
            "sub": str(uuid.uuid4()),
            "kind": "access",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        }
        wrong_token = pyjwt.encode(payload, "wrong-secret", algorithm="HS256")
        
        with pytest.raises(TokenError, match="Invalid"):
            decode_access_token(wrong_token)

    def test_decode_refresh_token_succeeds_with_valid_token(self):
        user_id = str(uuid.uuid4())
        token = create_refresh_token(user_id)
        
        payload = decode_refresh_token(token)
        
        assert payload["sub"] == user_id
        assert payload["kind"] == "refresh"

    def test_decode_refresh_token_rejects_access_token(self):
        user_id = str(uuid.uuid4())
        token = create_access_token(user_id, "test@example.com")
        
        with pytest.raises(TokenError, match="not a refresh token"):
            decode_refresh_token(token)

    def test_decode_refresh_token_rejects_expired_token(self):
        user_id = str(uuid.uuid4())
        with patch("app.core.security._REFRESH_EXPIRE", timedelta(seconds=-1)):
            token = create_refresh_token(user_id)
        
        with pytest.raises(TokenError, match="expired"):
            decode_refresh_token(token)
