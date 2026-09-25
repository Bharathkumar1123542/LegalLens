"""
User ORM model — LegalLens
Implements: architecture.md §7.2 `users` table schema exactly.
Columns: id, email, password_hash, full_name, role, is_active, created_at, updated_at.
Phase 9: Added MFA support — mfa_enabled, mfa_secret, mfa_backup_codes, mfa_setup_at.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, Enum as SAEnum, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    # argon2id hash — plaintext never stored (code-standards.md §Security)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        SAEnum("user", "admin", name="user_role_enum"),
        nullable=False,
        server_default="user",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    
    # ── MFA fields (Phase 9) ──────────────────────────────────────────────────
    mfa_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        index=True,
    )
    mfa_secret: Mapped[Optional[str]] = mapped_column(
        String(32),  # Base32-encoded TOTP secret (16 bytes = 26 chars base32)
        nullable=True,
    )
    mfa_backup_codes: Mapped[Optional[dict]] = mapped_column(
        JSONB,  # Array of hashed backup codes
        nullable=True,
    )
    mfa_setup_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # ── Account lockout fields (Phase 9) ──────────────────────────────────────
    failed_login_attempts: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        server_default=text("0"),
    )
    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    last_failed_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        # Deliberately excludes password_hash and mfa_secret (code-standards.md §Security)
        return f"<User id={self.id} email={self.email!r} role={self.role!r} mfa_enabled={self.mfa_enabled}>"
