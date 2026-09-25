"""
Unit tests for MFA Service — Phase 9
Tests TOTP generation, verification, backup codes, and MFA lifecycle.
"""

from __future__ import annotations

import pytest
import pyotp
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from app.services.mfa import mfa_service, pwd_context
from app.models.user import User


class TestMFAService:
    """Test MFA service functions."""
    
    def test_generate_secret(self):
        """Test TOTP secret generation."""
        secret = mfa_service.generate_secret()
        
        # Should be base32 string
        assert isinstance(secret, str)
        # Should be valid base32 (26 characters for 16 bytes)
        assert len(secret) >= 16
        # Should be uppercase alphanumeric
        assert secret.replace("=", "").isalnum()
        assert secret.isupper()
    
    def test_generate_provisioning_uri(self):
        """Test QR code URI generation."""
        secret = "JBSWY3DPEHPK3PXP"  # Valid base32 secret
        email = "test@example.com"
        
        uri = mfa_service.generate_provisioning_uri(secret, email)
        
        # Should be otpauth:// URI
        assert uri.startswith("otpauth://totp/")
        assert "LegalLens" in uri
        assert email in uri
        assert f"secret={secret}" in uri
    
    def test_generate_qr_code(self):
        """Test QR code image generation."""
        uri = "otpauth://totp/LegalLens:test@example.com?secret=JBSWY3DPEHPK3PXP&issuer=LegalLens"
        
        qr_bytes = mfa_service.generate_qr_code(uri)
        
        # Should be PNG image bytes
        assert isinstance(qr_bytes, bytes)
        assert len(qr_bytes) > 0
        # PNG magic bytes
        assert qr_bytes[:8] == b'\x89PNG\r\n\x1a\n'
    
    def test_verify_totp_valid(self):
        """Test TOTP token verification with valid token."""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        token = totp.now()
        
        # Should verify current token
        assert mfa_service.verify_totp(secret, token) is True
    
    def test_verify_totp_invalid_format(self):
        """Test TOTP token verification with invalid format."""
        secret = pyotp.random_base32()
        
        # Invalid formats
        assert mfa_service.verify_totp(secret, "12345") is False  # Too short
        assert mfa_service.verify_totp(secret, "1234567") is False  # Too long
        assert mfa_service.verify_totp(secret, "abcdef") is False  # Not digits
        assert mfa_service.verify_totp(secret, "") is False  # Empty
    
    def test_verify_totp_invalid_token(self):
        """Test TOTP token verification with invalid token."""
        secret = pyotp.random_base32()
        
        # Random 6-digit token (very unlikely to match)
        assert mfa_service.verify_totp(secret, "000000") is False
    
    def test_generate_backup_codes(self):
        """Test backup code generation."""
        codes = mfa_service.generate_backup_codes(count=10)
        
        # Should generate 10 codes
        assert len(codes) == 10
        
        # All codes should be unique
        assert len(set(codes)) == 10
        
        # Each code should be XXXX-XXXX format
        for code in codes:
            assert len(code) == 9  # 8 chars + 1 dash
            assert code[4] == "-"
            assert code[:4].isalnum()
            assert code[5:].isalnum()
            assert code.isupper()
    
    def test_hash_backup_codes(self):
        """Test backup code hashing."""
        codes = ["ABCD-1234", "EFGH-5678"]
        
        hashed = mfa_service.hash_backup_codes(codes)
        
        # Should return list of hashes
        assert len(hashed) == 2
        
        # Each hash should be bcrypt format ($2b$...)
        for h in hashed:
            assert h.startswith("$2b$")
    
    def test_verify_backup_code_valid(self):
        """Test backup code verification with valid code."""
        codes = ["ABCD-1234", "EFGH-5678"]
        hashed = mfa_service.hash_backup_codes(codes)
        
        # Should find first code
        matched = mfa_service.verify_backup_code("ABCD-1234", hashed)
        assert matched == hashed[0]
        
        # Should find second code
        matched = mfa_service.verify_backup_code("EFGH-5678", hashed)
        assert matched == hashed[1]
    
    def test_verify_backup_code_invalid(self):
        """Test backup code verification with invalid code."""
        codes = ["ABCD-1234"]
        hashed = mfa_service.hash_backup_codes(codes)
        
        # Should not match wrong code
        matched = mfa_service.verify_backup_code("WRONG-CODE", hashed)
        assert matched is None
    
    @pytest.mark.asyncio
    async def test_setup_mfa(self):
        """Test MFA setup flow."""
        user = MagicMock(spec=User)
        user.id = "test-user-id"
        user.email = "test@example.com"
        user.mfa_enabled = False
        
        session = AsyncMock()
        
        secret, backup_codes, qr_uri = await mfa_service.setup_mfa(user, session)
        
        # Should return secret, backup codes, QR URI
        assert isinstance(secret, str)
        assert len(backup_codes) == 10
        assert qr_uri.startswith("otpauth://totp/")
        
        # Should update user (but not enable yet)
        assert user.mfa_secret == secret
        assert user.mfa_backup_codes == {"codes": mfa_service.hash_backup_codes(backup_codes)}
        assert user.mfa_enabled is False
    
    @pytest.mark.asyncio
    async def test_enable_mfa_valid_token(self):
        """Test enabling MFA with valid token."""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        token = totp.now()
        
        user = MagicMock(spec=User)
        user.id = "test-user-id"
        user.mfa_secret = secret
        user.mfa_enabled = False
        
        session = AsyncMock()
        
        success = await mfa_service.enable_mfa(user, token, session)
        
        # Should enable MFA
        assert success is True
        assert user.mfa_enabled is True
        assert user.mfa_setup_at is not None
        assert isinstance(user.mfa_setup_at, datetime)
    
    @pytest.mark.asyncio
    async def test_enable_mfa_invalid_token(self):
        """Test enabling MFA with invalid token."""
        secret = pyotp.random_base32()
        
        user = MagicMock(spec=User)
        user.id = "test-user-id"
        user.mfa_secret = secret
        user.mfa_enabled = False
        
        session = AsyncMock()
        
        success = await mfa_service.enable_mfa(user, "000000", session)
        
        # Should not enable MFA
        assert success is False
        assert user.mfa_enabled is False
    
    @pytest.mark.asyncio
    async def test_enable_mfa_no_secret(self):
        """Test enabling MFA without secret."""
        user = MagicMock(spec=User)
        user.id = "test-user-id"
        user.mfa_secret = None
        user.mfa_enabled = False
        
        session = AsyncMock()
        
        success = await mfa_service.enable_mfa(user, "123456", session)
        
        # Should fail
        assert success is False
    
    @pytest.mark.asyncio
    async def test_disable_mfa(self):
        """Test disabling MFA."""
        user = MagicMock(spec=User)
        user.id = "test-user-id"
        user.mfa_enabled = True
        user.mfa_secret = "JBSWY3DPEHPK3PXP"
        user.mfa_backup_codes = {"codes": ["hash1", "hash2"]}
        user.mfa_setup_at = datetime.now(timezone.utc)
        
        session = AsyncMock()
        
        await mfa_service.disable_mfa(user, session)
        
        # Should clear MFA data
        assert user.mfa_enabled is False
        assert user.mfa_secret is None
        assert user.mfa_backup_codes is None
        # Keep setup_at for audit trail
        assert user.mfa_setup_at is not None
    
    @pytest.mark.asyncio
    async def test_verify_mfa_token_totp(self):
        """Test MFA token verification with TOTP."""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        token = totp.now()
        
        user = MagicMock(spec=User)
        user.id = "test-user-id"
        user.mfa_enabled = True
        user.mfa_secret = secret
        
        session = AsyncMock()
        
        is_valid, used_hash = await mfa_service.verify_mfa_token(user, token, session)
        
        # Should verify TOTP
        assert is_valid is True
        assert used_hash is None  # TOTP, not backup code
    
    @pytest.mark.asyncio
    async def test_verify_mfa_token_backup_code(self):
        """Test MFA token verification with backup code."""
        secret = pyotp.random_base32()
        backup_codes = ["ABCD-1234", "EFGH-5678"]
        hashed_codes = mfa_service.hash_backup_codes(backup_codes)
        
        user = MagicMock(spec=User)
        user.id = "test-user-id"
        user.mfa_enabled = True
        user.mfa_secret = secret
        user.mfa_backup_codes = {"codes": hashed_codes}
        
        session = AsyncMock()
        
        is_valid, used_hash = await mfa_service.verify_mfa_token(
            user, "ABCD-1234", session
        )
        
        # Should verify backup code
        assert is_valid is True
        assert used_hash == hashed_codes[0]
    
    @pytest.mark.asyncio
    async def test_verify_mfa_token_invalid(self):
        """Test MFA token verification with invalid token."""
        secret = pyotp.random_base32()
        
        user = MagicMock(spec=User)
        user.id = "test-user-id"
        user.mfa_enabled = True
        user.mfa_secret = secret
        user.mfa_backup_codes = {"codes": []}
        
        session = AsyncMock()
        
        is_valid, used_hash = await mfa_service.verify_mfa_token(
            user, "000000", session
        )
        
        # Should fail
        assert is_valid is False
        assert used_hash is None
    
    @pytest.mark.asyncio
    async def test_verify_mfa_token_mfa_not_enabled(self):
        """Test MFA token verification when MFA not enabled."""
        user = MagicMock(spec=User)
        user.id = "test-user-id"
        user.mfa_enabled = False
        
        session = AsyncMock()
        
        is_valid, used_hash = await mfa_service.verify_mfa_token(
            user, "123456", session
        )
        
        # Should fail
        assert is_valid is False
        assert used_hash is None
