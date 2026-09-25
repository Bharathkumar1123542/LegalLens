"""
MFA routes — LegalLens API v1 (Phase 9)
Multi-factor authentication endpoints.

Endpoints:
  POST /auth/mfa/setup              → Setup MFA (get QR code + backup codes)
  POST /auth/mfa/verify-setup       → Verify token and enable MFA
  POST /auth/mfa/verify             → Verify MFA token during login
  GET  /auth/mfa/status             → Get MFA status
  POST /auth/mfa/disable            → Disable MFA
  POST /auth/mfa/backup-codes/regenerate → Regenerate backup codes

Security:
- Rate limiting on all endpoints
- Password verification required for disable
- TOTP token required for sensitive operations
- Backup codes hashed with bcrypt
"""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.rate_limiter import limiter, RateLimits
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.mfa import (
    MFADisableRequest,
    MFADisableResponse,
    MFALoginRequest,
    MFALoginResponse,
    MFARegenerateBackupCodesRequest,
    MFARegenerateBackupCodesResponse,
    MFASetupResponse,
    MFAStatusResponse,
    MFAVerifySetupRequest,
    MFAVerifySetupResponse,
)
from app.schemas.auth import TokenPair
from app.services.mfa import mfa_service

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth/mfa", tags=["mfa"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


# ── MFA Setup ──────────────────────────────────────────────────────────────────


@router.post(
    "/setup",
    response_model=MFASetupResponse,
    status_code=status.HTTP_200_OK,
    summary="Initiate MFA setup (get QR code + backup codes)",
)
@limiter.limit(RateLimits.AUTH_REGISTER)  # Reuse register rate limit (5/hour)
async def setup_mfa(
    request: Request,
    current_user: CurrentUserDep,
    db: DbDep,
) -> MFASetupResponse:
    """
    Generate TOTP secret and backup codes for MFA setup.
    
    Flow:
    1. Call this endpoint to get secret + QR code URI + backup codes
    2. Scan QR code in authenticator app (Google Authenticator, Authy, etc.)
    3. Call POST /auth/mfa/verify-setup with 6-digit token to enable MFA
    
    Notes:
    - MFA is NOT enabled yet (requires verification)
    - Save backup codes securely (shown once)
    - QR code URI format: otpauth://totp/LegalLens:user@example.com?secret=...
    """
    if current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is already enabled. Disable first to re-setup.",
        )
    
    secret, backup_codes, qr_uri = await mfa_service.setup_mfa(current_user, db)
    await db.commit()
    
    log.info("mfa_setup_started", user_id=str(current_user.id))
    
    return MFASetupResponse(
        secret=secret,
        qr_code_uri=qr_uri,
        backup_codes=backup_codes,
    )


@router.post(
    "/verify-setup",
    response_model=MFAVerifySetupResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify token and enable MFA",
)
@limiter.limit(RateLimits.AUTH_LOGIN)  # 20/hour rate limit
async def verify_setup(
    request: Request,
    body: MFAVerifySetupRequest,
    current_user: CurrentUserDep,
    db: DbDep,
) -> MFAVerifySetupResponse:
    """
    Complete MFA setup by verifying a token from authenticator app.
    
    Flow:
    1. After calling POST /auth/mfa/setup and scanning QR code
    2. Enter 6-digit token from authenticator app
    3. If valid, MFA is enabled
    
    Notes:
    - Token must be valid (6 digits from authenticator app)
    - MFA secret must exist (from POST /auth/mfa/setup)
    - Once enabled, future logins will require MFA token
    """
    if current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is already enabled.",
        )
    
    if not current_user.mfa_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA setup not initiated. Call POST /auth/mfa/setup first.",
        )
    
    # Verify token
    success = await mfa_service.enable_mfa(current_user, body.token, db)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA token. Please try again.",
        )
    
    await db.commit()
    
    log.info("mfa_enabled", user_id=str(current_user.id))
    
    return MFAVerifySetupResponse(mfa_enabled=True)


# ── MFA Login Verification ─────────────────────────────────────────────────────


@router.post(
    "/verify",
    response_model=MFALoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify MFA token during login",
)
@limiter.limit(RateLimits.AUTH_LOGIN)  # 20/hour rate limit
async def verify_mfa_login(
    request: Request,
    body: MFALoginRequest,
    db: DbDep,
) -> MFALoginResponse:
    """
    Complete login by verifying MFA token.
    
    Flow:
    1. Call POST /auth/login with email/password
    2. If response has mfa_required=true, call this endpoint
    3. Provide 6-digit TOTP token or 8-character backup code
    4. Receive access + refresh tokens
    
    Notes:
    - User ID from previous login attempt (stored in session/cookie)
    - For now, expects email in request (Phase 10: use session)
    - Backup codes are single-use (removed after successful verification)
    
    TODO Phase 10: Store pending MFA user_id in Redis session instead of requiring email
    """
    # TEMPORARY: Require email to identify user
    # Phase 10 improvement: Store user_id in Redis session after password verification
    email = request.headers.get("X-MFA-Email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-MFA-Email header. This is a temporary requirement for Phase 9.",
        )
    
    # Get user
    result = await db.execute(select(User).where(User.email == email.lower()))
    user: User | None = result.scalar_one_or_none()
    
    if not user or not user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="MFA not enabled for this account.",
        )
    
    # Verify token
    is_valid, used_backup_hash = await mfa_service.verify_mfa_token(
        user, body.token, db
    )
    
    if not is_valid:
        log.warning("mfa_verification_failed", user_id=str(user.id))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA token or backup code.",
        )
    
    # Remove used backup code
    backup_code_used = False
    remaining_codes = None
    
    if used_backup_hash:
        backup_code_used = True
        if user.mfa_backup_codes and "codes" in user.mfa_backup_codes:
            codes = user.mfa_backup_codes["codes"]
            codes.remove(used_backup_hash)
            user.mfa_backup_codes = {"codes": codes}
            remaining_codes = len(codes)
            
            log.info(
                "mfa_backup_code_used",
                user_id=str(user.id),
                remaining=remaining_codes,
            )
    
    await db.commit()
    
    # Issue tokens
    access_token = create_access_token(str(user.id), user.email)
    refresh_token = create_refresh_token(str(user.id))
    
    log.info("mfa_login_successful", user_id=str(user.id))
    
    return MFALoginResponse(
        access_token=access_token,
        token_type="bearer",
        backup_code_used=backup_code_used,
        remaining_backup_codes=remaining_codes,
    )


# ── MFA Status ─────────────────────────────────────────────────────────────────


@router.get(
    "/status",
    response_model=MFAStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get MFA status for current user",
)
@limiter.limit(RateLimits.DOCUMENT_LIST)  # 200/minute (read operation)
async def get_mfa_status(
    request: Request,
    current_user: CurrentUserDep,
    db: DbDep,
) -> MFAStatusResponse:
    """
    Check if MFA is enabled and get backup code count.
    
    Returns:
    - mfa_enabled: True if MFA is active
    - mfa_setup_at: When MFA was enabled (None if never enabled)
    - backup_codes_remaining: Number of unused backup codes
    """
    backup_codes_remaining = None
    if current_user.mfa_enabled and current_user.mfa_backup_codes:
        if "codes" in current_user.mfa_backup_codes:
            backup_codes_remaining = len(current_user.mfa_backup_codes["codes"])
    
    return MFAStatusResponse(
        mfa_enabled=current_user.mfa_enabled,
        mfa_setup_at=current_user.mfa_setup_at,
        backup_codes_remaining=backup_codes_remaining,
    )


# ── MFA Disable ────────────────────────────────────────────────────────────────


@router.post(
    "/disable",
    response_model=MFADisableResponse,
    status_code=status.HTTP_200_OK,
    summary="Disable MFA for current user",
)
@limiter.limit(RateLimits.AUTH_REGISTER)  # 5/hour (sensitive operation)
async def disable_mfa(
    request: Request,
    body: MFADisableRequest,
    current_user: CurrentUserDep,
    db: DbDep,
) -> MFADisableResponse:
    """
    Disable MFA (requires password + MFA token confirmation).
    
    Security:
    - Requires current password
    - Requires valid MFA token (TOTP or backup code)
    - Rate limited to 5/hour
    
    Notes:
    - Clears mfa_secret and mfa_backup_codes
    - Sets mfa_enabled = False
    - Keeps mfa_setup_at for audit trail
    """
    if not current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is not enabled.",
        )
    
    # Verify password
    if not verify_password(body.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password.",
        )
    
    # Verify MFA token
    is_valid, _ = await mfa_service.verify_mfa_token(
        current_user, body.token, db
    )
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MFA token.",
        )
    
    # Disable MFA
    await mfa_service.disable_mfa(current_user, db)
    await db.commit()
    
    log.info("mfa_disabled", user_id=str(current_user.id))
    
    return MFADisableResponse()


# ── Regenerate Backup Codes ────────────────────────────────────────────────────


@router.post(
    "/backup-codes/regenerate",
    response_model=MFARegenerateBackupCodesResponse,
    status_code=status.HTTP_200_OK,
    summary="Regenerate backup codes",
)
@limiter.limit(RateLimits.AUTH_REGISTER)  # 5/hour (sensitive operation)
async def regenerate_backup_codes(
    request: Request,
    body: MFARegenerateBackupCodesRequest,
    current_user: CurrentUserDep,
    db: DbDep,
) -> MFARegenerateBackupCodesResponse:
    """
    Generate new backup codes (requires TOTP token).
    
    Security:
    - Requires valid TOTP token (not backup code)
    - Invalidates all existing backup codes
    - Rate limited to 5/hour
    
    Use Cases:
    - Used all backup codes
    - Lost backup codes
    - Security concern (suspect codes compromised)
    
    Notes:
    - MUST verify with TOTP token (6 digits from app)
    - Cannot use backup code to regenerate (chicken-egg problem)
    - Save new codes securely (shown once)
    """
    if not current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA is not enabled.",
        )
    
    # Verify TOTP token (not backup code)
    if not mfa_service.verify_totp(current_user.mfa_secret, body.token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid TOTP token. Backup codes cannot be used for this operation.",
        )
    
    # Generate new backup codes
    new_codes = mfa_service.generate_backup_codes(count=10)
    hashed_codes = mfa_service.hash_backup_codes(new_codes)
    
    # Replace old codes
    current_user.mfa_backup_codes = {"codes": hashed_codes}
    await db.commit()
    
    log.info("mfa_backup_codes_regenerated", user_id=str(current_user.id))
    
    return MFARegenerateBackupCodesResponse(backup_codes=new_codes)
