"""
Auth routes — LegalLens API v1
Implements: architecture.md §8 /auth/* endpoints.
  POST /auth/register  → 201 RegisterResponse
  POST /auth/login     → 200 TokenPair
  POST /auth/refresh   → 200 TokenPair

code-standards.md §Security:
  - Request validated by Pydantic schemas (rejects invalid before any DB call)
  - No PII in log lines (user_id only, never email or password)
  - 401 on wrong credentials — no distinction email vs password (user enumeration prevention)
  
Phase 8: Rate limiting applied to prevent brute force attacks
"""

from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limiter import limiter, RateLimits
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenPair,
    UserProfile,
)
from app.services import auth as auth_service
from app.services.captcha import captcha_service

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user account",
)
@limiter.limit(RateLimits.AUTH_REGISTER)
async def register(
    request: Request,
    body: RegisterRequest,
    db: DbDep,
) -> RegisterResponse:
    """
    Phase 9: CAPTCHA-protected registration.
    
    - Verifies hCaptcha token if CAPTCHA enabled
    - Rate limited to 5 registrations per hour
    - Returns user profile + JWT tokens
    
    CAPTCHA can be bypassed in development by:
    - Setting CAPTCHA_ENABLED=False in .env
    - Or omitting CAPTCHA_SECRET_KEY
    """
    # Phase 9: Verify CAPTCHA
    if captcha_service.is_enabled():
        if not body.captcha_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CAPTCHA token is required. Please complete the CAPTCHA challenge.",
            )
        
        ip = request.client.host if request.client else None
        is_valid, error_message = await captcha_service.verify_captcha(
            body.captcha_token,
            remote_ip=ip,
        )
        
        if not is_valid:
            log.warning(
                "registration_captcha_failed",
                ip=ip,
                error=error_message,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_message or "CAPTCHA verification failed.",
            )
    
    # Proceed with registration
    user, tokens = await auth_service.register_user(
        db=db,
        email=body.email,
        password=body.password,
        full_name=body.full_name,
    )
    await db.commit()
    return RegisterResponse(user=UserProfile.model_validate(user), tokens=tokens)


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Exchange credentials for a token pair (or MFA prompt)",
)
@limiter.limit(RateLimits.AUTH_LOGIN)
async def login(
    request: Request,
    body: LoginRequest,
    db: DbDep,
) -> LoginResponse:
    """
    Phase 9: MFA-aware login.
    
    - If MFA disabled: Returns tokens immediately
    - If MFA enabled: Returns mfa_required=True, client must call POST /auth/mfa/verify
    """
    user, tokens = await auth_service.authenticate_user(
        db=db,
        email=body.email,
        password=body.password,
    )
    await db.commit()  # may have written a rehashed password
    
    if tokens is None:
        # MFA required
        return LoginResponse(
            mfa_required=True,
            tokens=None,
            message="MFA token required. Please provide your 6-digit code or backup code.",
        )
    
    # No MFA, return tokens
    return LoginResponse(
        mfa_required=False,
        tokens=tokens,
    )


@router.post(
    "/refresh",
    response_model=TokenPair,
    status_code=status.HTTP_200_OK,
    summary="Exchange a refresh token for a new token pair",
)
@limiter.limit(RateLimits.AUTH_REFRESH)
async def refresh(
    request: Request,
    body: RefreshRequest,
    db: DbDep,
) -> TokenPair:
    tokens = await auth_service.refresh_access_token(
        db=db,
        refresh_token=body.refresh_token,
    )
    return tokens
