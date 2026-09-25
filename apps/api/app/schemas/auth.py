"""
Auth Pydantic schemas — LegalLens API
Implements: architecture.md §8 API contracts for /auth/* endpoints.
code-standards.md: password_hash never exposed in responses.
code-standards.md: legal disclaimer in every response schema is not in auth schemas
  (no LLM content here), but UserProfile deliberately omits password_hash.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator


# ── Request schemas ───────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    captcha_token: str | None = Field(
        None,
        description="hCaptcha response token (required if CAPTCHA enabled)",
    )

    @model_validator(mode="after")
    def password_not_trivial(self) -> "RegisterRequest":
        # Reject obviously weak passwords (Phase 6 will add full zxcvbn strength check)
        if self.password.lower() in {"password", "12345678", "password1"}:
            raise ValueError("Password is too common.")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


# ── Response schemas ──────────────────────────────────────────────────────────

class UserProfile(BaseModel):
    """Safe user representation — password_hash deliberately omitted."""
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenPair(BaseModel):
    """Returned by /auth/login and /auth/refresh."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expiry


class LoginResponse(BaseModel):
    """
    Response for /auth/login endpoint.
    Phase 9: Supports MFA flow.
    
    - If MFA disabled: Returns tokens immediately
    - If MFA enabled: Returns mfa_required=True, tokens=None
    """
    mfa_required: bool = Field(default=False, description="True if MFA token required")
    tokens: TokenPair | None = Field(None, description="Tokens (if MFA not required)")
    message: str | None = Field(None, description="Informational message")


class RegisterResponse(BaseModel):
    user: UserProfile
    tokens: TokenPair
