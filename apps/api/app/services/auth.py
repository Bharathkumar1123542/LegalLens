"""
Auth Service — LegalLens
Implements: architecture.md §6.1 Auth Module.
  Functions: register_user(), authenticate_user(), refresh_access_token()
code-standards.md:
  - Passwords hashed with argon2id only; never stored/logged in plaintext
  - Duplicate email → 409, not 500
  - Expired refresh token → 401
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    hash_password,
    verify_password,
    needs_rehash,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    TokenError,
)
from app.core.config import settings
from app.models.user import User
from app.schemas.auth import TokenPair, UserProfile
from app.services.account_lockout import lockout_service

log = structlog.get_logger(__name__)


def _make_token_pair(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(str(user.id), user.email),
        refresh_token=create_refresh_token(str(user.id)),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def register_user(
    db: AsyncSession,
    email: str,
    password: str,
    full_name: str,
) -> tuple[User, TokenPair]:
    """
    Create a new user account.
    Raises 409 if the email is already registered.
    Returns (User, TokenPair) — caller logs the audit event.
    """
    # Check for existing email (advisory pre-check; unique constraint is authoritative)
    existing = await db.execute(select(User).where(User.email == email.lower()))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    # Hash password — plaintext is discarded after this line (code-standards.md §Security)
    pw_hash = hash_password(password)

    user = User(
        id=uuid.uuid4(),
        email=email.lower(),
        password_hash=pw_hash,
        full_name=full_name,
        role="user",
        is_active=True,
    )
    db.add(user)

    try:
        await db.flush()  # surface unique-constraint violation before commit
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    log.info("user.registered", user_id=str(user.id))  # no PII in log (code-standards.md)
    return user, _make_token_pair(user)


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> tuple[User, TokenPair | None]:
    """
    Validate credentials and issue a token pair (or require MFA).
    
    Phase 9 updates:
    - Account lockout: Locks account after 5 failed attempts for 15 minutes
    - MFA flow: Returns (user, None) if MFA enabled
    
    Raises 401 on any failure (no distinction between wrong email/wrong password
    to avoid user enumeration — code-standards.md §Security).
    Raises 403 if account is locked or deactivated.
    Upgrades the hash on-the-fly if argon2id parameters have been strengthened.
    """
    result = await db.execute(select(User).where(User.email == email.lower()))
    user: User | None = result.scalar_one_or_none()

    # Phase 9: Check if account is locked
    if user and lockout_service.is_locked(user):
        remaining_time = lockout_service.get_remaining_lockout_time(user)
        minutes_remaining = int(remaining_time.total_seconds() / 60) if remaining_time else 0
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is temporarily locked due to multiple failed login attempts. Try again in {minutes_remaining} minutes.",
        )

    # Constant-time comparison — evaluate hash even on miss to avoid timing attacks
    _DUMMY_HASH = hash_password("dummy-constant-time-placeholder")
    candidate_hash = user.password_hash if user else _DUMMY_HASH

    if not verify_password(password, candidate_hash) or user is None:
        # Phase 9: Record failed attempt
        if user:
            is_locked, attempts, locked_until = lockout_service.record_failed_login(user)
            # Note: Transaction will be committed by caller
            
            if is_locked:
                # Account just got locked
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Account locked due to {attempts} failed login attempts. Try again in 15 minutes.",
                )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )

    # Phase 9: Reset failed attempts on successful login
    lockout_service.reset_failed_attempts(user)

    # Transparent hash upgrade if parameters have been strengthened
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        log.info("user.password_rehashed", user_id=str(user.id))

    # Phase 9: Check if MFA is enabled
    if user.mfa_enabled:
        log.info("user.login_mfa_required", user_id=str(user.id))
        return user, None  # Caller must prompt for MFA token
    
    log.info("user.login", user_id=str(user.id))
    return user, _make_token_pair(user)


async def refresh_access_token(
    db: AsyncSession,
    refresh_token: str,
) -> TokenPair:
    """
    Exchange a valid refresh token for a new token pair.
    Raises 401 on expired or invalid token.
    """
    try:
        payload = decode_refresh_token(refresh_token)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user: User | None = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated.",
        )

    log.info("user.token_refreshed", user_id=str(user.id))
    return _make_token_pair(user)
