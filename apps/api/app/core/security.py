"""
Security utilities — LegalLens API
Implements:
  - architecture.md §4: JWT (access + refresh), argon2id hashing
  - architecture.md §9: ACCESS_TOKEN_EXPIRE_MINUTES=15, REFRESH_TOKEN_EXPIRE_DAYS=14
  - code-standards.md: plaintext password never logged or persisted; argon2id only
  - code-standards.md: JWT secret loaded only from Settings (never from env ad-hoc)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from app.core.config import settings

# ── Password hashing ──────────────────────────────────────────────────────────
# Argon2id with OWASP-recommended parameters (time_cost=2, memory_cost=65536, parallelism=1)
_ph = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=1, hash_len=32, salt_len=16)


def hash_password(plaintext: str) -> str:
    """Return an argon2id hash. Plaintext is never stored or logged."""
    return _ph.hash(plaintext)


def verify_password(plaintext: str, hashed: str) -> bool:
    """Return True if plaintext matches the stored argon2id hash."""
    try:
        return _ph.verify(hashed, plaintext)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    """True if the stored hash was made with weaker parameters and should be upgraded."""
    return _ph.check_needs_rehash(hashed)


# ── JWT ───────────────────────────────────────────────────────────────────────
TokenKind = Literal["access", "refresh"]

_ACCESS_EXPIRE = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
_REFRESH_EXPIRE = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)


def _create_token(
    subject: str,
    kind: TokenKind,
    extra_claims: dict | None = None,
) -> str:
    """
    Create a signed JWT.
    - `sub`  : user UUID (str)
    - `kind` : "access" or "refresh" — prevents refresh tokens being used as access tokens
    - `jti`  : unique token ID for future blocklist support (Phase 6)
    """
    expire = datetime.now(timezone.utc) + (
        _ACCESS_EXPIRE if kind == "access" else _REFRESH_EXPIRE
    )
    payload: dict = {
        "sub": subject,
        "kind": kind,
        "jti": str(uuid.uuid4()),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(
        payload,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_access_token(user_id: str, email: str) -> str:
    """Issue a 15-minute access token carrying the user's email as a non-authoritative claim."""
    return _create_token(user_id, "access", extra_claims={"email": email})


def create_refresh_token(user_id: str) -> str:
    """Issue a 14-day refresh token. Contains no PII beyond the user ID."""
    return _create_token(user_id, "refresh")


class TokenError(Exception):
    """Raised for any JWT verification failure (expired, tampered, wrong kind)."""


def decode_access_token(token: str) -> dict:
    """
    Decode and validate an access token.
    Raises TokenError on any failure — caller converts to 401.
    Returns the full payload dict.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except ExpiredSignatureError:
        raise TokenError("Access token has expired.")
    except InvalidTokenError as exc:
        raise TokenError(f"Invalid access token: {exc}") from exc

    if payload.get("kind") != "access":
        raise TokenError("Token is not an access token.")
    return payload


def decode_refresh_token(token: str) -> dict:
    """
    Decode and validate a refresh token.
    Raises TokenError on any failure.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except ExpiredSignatureError:
        raise TokenError("Refresh token has expired — please log in again.")
    except InvalidTokenError as exc:
        raise TokenError(f"Invalid refresh token: {exc}") from exc

    if payload.get("kind") != "refresh":
        raise TokenError("Token is not a refresh token.")
    return payload
