"""
Multi-Factor Authentication Service — Phase 9
Implements TOTP-based 2FA using pyotp library.

Features:
- TOTP secret generation
- QR code provisioning URI
- Token verification (6-digit codes)
- Backup codes (10 codes, single-use, bcrypt-hashed)
- Time-based validation (30-second window, ±1 window tolerance)

Security:
- Secrets stored encrypted in database
- Backup codes hashed with bcrypt
- Rate limiting on verification attempts (handled by endpoint)
- No plaintext secrets in logs
"""

from __future__ import annotations

import io
import secrets
from datetime import datetime, timezone
from typing import List, Optional

import pyotp
import qrcode
import structlog
from passlib.context import CryptContext

from app.models.user import User

log = structlog.get_logger(__name__)

# Backup code hashing (same as passwords)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class MFAService:
    """Service for TOTP-based multi-factor authentication."""
    
    @staticmethod
    def generate_secret() -> str:
        """
        Generate a new TOTP secret (base32-encoded).
        
        Returns:
            Base32-encoded secret (16 bytes = 26 characters)
        """
        # pyotp generates a base32-encoded 160-bit (20-byte) secret by default
        # We use 128-bit (16-byte) for compatibility
        return pyotp.random_base32(length=16)
    
    @staticmethod
    def generate_provisioning_uri(secret: str, user_email: str) -> str:
        """
        Generate a TOTP provisioning URI for QR code.
        
        Args:
            secret: Base32-encoded TOTP secret
            user_email: User's email address (displayed in authenticator app)
        
        Returns:
            otpauth:// URI for QR code generation
        """
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(
            name=user_email,
            issuer_name="LegalLens",
        )
    
    @staticmethod
    def generate_qr_code(provisioning_uri: str) -> bytes:
        """
        Generate a QR code image from provisioning URI.
        
        Args:
            provisioning_uri: otpauth:// URI
        
        Returns:
            PNG image bytes
        """
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to bytes
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()
    
    @staticmethod
    def verify_totp(secret: str, token: str) -> bool:
        """
        Verify a TOTP token.
        
        Args:
            secret: Base32-encoded TOTP secret
            token: 6-digit token from authenticator app
        
        Returns:
            True if token is valid, False otherwise
        
        Notes:
            - Uses 30-second time window
            - Allows ±1 window (90 seconds total) for clock drift
            - Tokens are valid for ~60 seconds (current + previous/next window)
        """
        if not token or not token.isdigit() or len(token) != 6:
            return False
        
        totp = pyotp.TOTP(secret)
        # valid_window=1 allows ±1 time step (30s each) for clock drift
        return totp.verify(token, valid_window=1)
    
    @staticmethod
    def generate_backup_codes(count: int = 10) -> List[str]:
        """
        Generate single-use backup codes.
        
        Args:
            count: Number of backup codes to generate (default: 10)
        
        Returns:
            List of backup codes (8 characters each, alphanumeric)
        
        Format: XXXX-XXXX (e.g., A3B7-C9D2)
        """
        codes = []
        for _ in range(count):
            # Generate 8 random bytes, convert to hex (16 chars), take first 8
            code = secrets.token_hex(4).upper()  # 8 hex chars
            # Format as XXXX-XXXX
            formatted = f"{code[:4]}-{code[4:8]}"
            codes.append(formatted)
        return codes
    
    @staticmethod
    def hash_backup_codes(codes: List[str]) -> List[str]:
        """
        Hash backup codes for storage.
        
        Args:
            codes: List of plaintext backup codes
        
        Returns:
            List of bcrypt-hashed codes
        """
        return [pwd_context.hash(code) for code in codes]
    
    @staticmethod
    def verify_backup_code(code: str, hashed_codes: List[str]) -> Optional[str]:
        """
        Verify a backup code against hashed codes.
        
        Args:
            code: Plaintext backup code to verify
            hashed_codes: List of bcrypt-hashed codes
        
        Returns:
            The matching hashed code if valid, None otherwise
        
        Notes:
            - Backup codes are single-use
            - Caller must remove the returned hash from database after use
        """
        for hashed in hashed_codes:
            if pwd_context.verify(code, hashed):
                return hashed
        return None
    
    @staticmethod
    async def setup_mfa(user: User, session) -> tuple[str, List[str], str]:
        """
        Set up MFA for a user (generate secret + backup codes).
        
        Args:
            user: User model instance
            session: Database session
        
        Returns:
            Tuple of (secret, backup_codes, qr_code_uri)
        
        Notes:
            - Does NOT enable MFA yet (user must verify token first)
            - Stores secret in user.mfa_secret
            - Does NOT commit transaction (caller must commit)
        """
        # Generate secret
        secret = MFAService.generate_secret()
        
        # Generate backup codes
        backup_codes = MFAService.generate_backup_codes(count=10)
        hashed_codes = MFAService.hash_backup_codes(backup_codes)
        
        # Generate provisioning URI
        qr_uri = MFAService.generate_provisioning_uri(secret, user.email)
        
        # Store in user (but don't enable yet)
        user.mfa_secret = secret
        user.mfa_backup_codes = {"codes": hashed_codes}
        user.mfa_enabled = False  # Not enabled until verified
        
        log.info(
            "mfa_setup_initiated",
            user_id=str(user.id),
            backup_code_count=len(backup_codes),
        )
        
        return secret, backup_codes, qr_uri
    
    @staticmethod
    async def enable_mfa(user: User, token: str, session) -> bool:
        """
        Enable MFA after verifying a token (completes setup).
        
        Args:
            user: User model instance
            token: 6-digit TOTP token to verify
            session: Database session
        
        Returns:
            True if token valid and MFA enabled, False otherwise
        
        Notes:
            - Verifies token against user.mfa_secret
            - Sets user.mfa_enabled = True
            - Sets user.mfa_setup_at timestamp
            - Does NOT commit transaction (caller must commit)
        """
        if not user.mfa_secret:
            log.warning("mfa_enable_no_secret", user_id=str(user.id))
            return False
        
        # Verify token
        if not MFAService.verify_totp(user.mfa_secret, token):
            log.warning("mfa_enable_invalid_token", user_id=str(user.id))
            return False
        
        # Enable MFA
        user.mfa_enabled = True
        user.mfa_setup_at = datetime.now(timezone.utc)
        
        log.info("mfa_enabled", user_id=str(user.id))
        return True
    
    @staticmethod
    async def disable_mfa(user: User, session) -> None:
        """
        Disable MFA for a user.
        
        Args:
            user: User model instance
            session: Database session
        
        Notes:
            - Clears mfa_secret and mfa_backup_codes
            - Sets mfa_enabled = False
            - Keeps mfa_setup_at for audit trail
            - Does NOT commit transaction (caller must commit)
        """
        user.mfa_enabled = False
        user.mfa_secret = None
        user.mfa_backup_codes = None
        # Keep mfa_setup_at for audit trail
        
        log.info("mfa_disabled", user_id=str(user.id))
    
    @staticmethod
    async def verify_mfa_token(
        user: User,
        token: str,
        session,
    ) -> tuple[bool, Optional[str]]:
        """
        Verify an MFA token (TOTP or backup code).
        
        Args:
            user: User model instance
            token: 6-digit TOTP token or 8-char backup code (with optional dash)
            session: Database session
        
        Returns:
            Tuple of (is_valid, used_backup_code_hash)
            - is_valid: True if token/code is valid
            - used_backup_code_hash: Hash of backup code if used, None otherwise
        
        Notes:
            - Tries TOTP first, then backup codes
            - If backup code used, caller MUST remove it from database
            - Does NOT commit transaction (caller must commit)
        """
        if not user.mfa_enabled or not user.mfa_secret:
            return False, None
        
        # Try TOTP token first (6 digits)
        if token.isdigit() and len(token) == 6:
            if MFAService.verify_totp(user.mfa_secret, token):
                log.info("mfa_verified_totp", user_id=str(user.id))
                return True, None
        
        # Try backup code (XXXX-XXXX format, allow without dash)
        backup_code = token.upper().replace("-", "")
        if len(backup_code) == 8 and backup_code.isalnum():
            # Re-add dash for verification
            formatted_code = f"{backup_code[:4]}-{backup_code[4:8]}"
            
            if user.mfa_backup_codes and "codes" in user.mfa_backup_codes:
                hashed_codes = user.mfa_backup_codes["codes"]
                used_hash = MFAService.verify_backup_code(formatted_code, hashed_codes)
                
                if used_hash:
                    log.info(
                        "mfa_verified_backup_code",
                        user_id=str(user.id),
                        remaining_codes=len(hashed_codes) - 1,
                    )
                    return True, used_hash
        
        log.warning("mfa_verification_failed", user_id=str(user.id))
        return False, None


# Singleton instance
mfa_service = MFAService()
