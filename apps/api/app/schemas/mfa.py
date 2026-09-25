"""
MFA Schemas — Phase 9
Request/response models for multi-factor authentication endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ── MFA Setup ──────────────────────────────────────────────────────────────────


class MFASetupResponse(BaseModel):
    """Response for POST /auth/mfa/setup"""
    
    secret: str = Field(..., description="Base32-encoded TOTP secret (store securely)")
    qr_code_uri: str = Field(..., description="otpauth:// URI for QR code generation")
    backup_codes: List[str] = Field(..., description="10 backup codes (display once, save securely)")
    message: str = Field(default="MFA setup initiated. Scan QR code and verify token to enable.")
    
    model_config = {"from_attributes": True}


class MFAVerifySetupRequest(BaseModel):
    """Request for POST /auth/mfa/verify-setup"""
    
    token: str = Field(..., min_length=6, max_length=6, description="6-digit TOTP token")


class MFAVerifySetupResponse(BaseModel):
    """Response for POST /auth/mfa/verify-setup"""
    
    mfa_enabled: bool = Field(..., description="MFA is now enabled")
    message: str = Field(default="MFA successfully enabled")
    
    model_config = {"from_attributes": True}


# ── MFA Login ──────────────────────────────────────────────────────────────────


class MFALoginRequest(BaseModel):
    """Request for POST /auth/mfa/verify (during login)"""
    
    token: str = Field(
        ...,
        description="6-digit TOTP token or 8-character backup code (XXXX-XXXX)",
        min_length=6,
        max_length=9,  # XXXX-XXXX with dash
    )


class MFALoginResponse(BaseModel):
    """Response for POST /auth/mfa/verify (during login)"""
    
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer")
    backup_code_used: bool = Field(
        default=False,
        description="True if backup code was used (warn user)",
    )
    remaining_backup_codes: Optional[int] = Field(
        None,
        description="Number of remaining backup codes (if backup used)",
    )
    
    model_config = {"from_attributes": True}


# ── MFA Status ─────────────────────────────────────────────────────────────────


class MFAStatusResponse(BaseModel):
    """Response for GET /auth/mfa/status"""
    
    mfa_enabled: bool = Field(..., description="Whether MFA is enabled")
    mfa_setup_at: Optional[datetime] = Field(None, description="When MFA was set up")
    backup_codes_remaining: Optional[int] = Field(
        None,
        description="Number of unused backup codes",
    )
    
    model_config = {"from_attributes": True}


# ── MFA Disable ────────────────────────────────────────────────────────────────


class MFADisableRequest(BaseModel):
    """Request for POST /auth/mfa/disable"""
    
    password: str = Field(..., description="Current password for confirmation")
    token: str = Field(
        ...,
        min_length=6,
        max_length=9,
        description="6-digit TOTP token or backup code",
    )


class MFADisableResponse(BaseModel):
    """Response for POST /auth/mfa/disable"""
    
    mfa_enabled: bool = Field(default=False, description="MFA is now disabled")
    message: str = Field(default="MFA successfully disabled")
    
    model_config = {"from_attributes": True}


# ── MFA Regenerate Backup Codes ────────────────────────────────────────────────


class MFARegenerateBackupCodesRequest(BaseModel):
    """Request for POST /auth/mfa/backup-codes/regenerate"""
    
    token: str = Field(
        ...,
        min_length=6,
        max_length=6,
        description="6-digit TOTP token (not backup code)",
    )


class MFARegenerateBackupCodesResponse(BaseModel):
    """Response for POST /auth/mfa/backup-codes/regenerate"""
    
    backup_codes: List[str] = Field(..., description="10 new backup codes")
    message: str = Field(default="Backup codes regenerated. Save these securely.")
    
    model_config = {"from_attributes": True}
