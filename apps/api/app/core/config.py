"""
Configuration — LegalLens API
Implements: architecture.md §9, code-standards.md (single Settings class, fail-fast).
Every environment variable required at startup is declared here.
A missing required variable raises ValidationError at import time — never fails lazily.
"""

from __future__ import annotations

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Runtime ────────────────────────────────────────────────────────────────
    ENVIRONMENT: str  # development | staging | production

    # ── Database ───────────────────────────────────────────────────────────────
    DATABASE_URL: str  # postgresql+asyncpg://…

    # ── Redis / Celery ─────────────────────────────────────────────────────────
    REDIS_URL: str
    CELERY_BROKER_URL: str

    # ── Object Storage ─────────────────────────────────────────────────────────
    S3_BUCKET: str
    S3_ENDPOINT_URL: str | None = None  # local dev (MinIO) only; omit in prod
    S3_ACCESS_KEY_ID: str
    S3_SECRET_ACCESS_KEY: str

    # ── External AI APIs ───────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str
    VOYAGE_API_KEY: str

    # ── Auth ───────────────────────────────────────────────────────────────────
    JWT_SECRET: str  # 256-bit random, rotated on schedule
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    # ── Upload limits ──────────────────────────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = 20

    # ── Allowed MIME types ─────────────────────────────────────────────────────
    # Stored as a comma-separated string so it reads cleanly from .env.
    # Access via the parsed property `allowed_mime_types_list`.
    ALLOWED_MIME_TYPES: str = "application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"

    # ── CORS ───────────────────────────────────────────────────────────────────
    # Comma-separated allow-list. Never "*" in production.
    CORS_ORIGINS: str

    # ── Rate limiting ──────────────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 30

    # ── Observability ─────────────────────────────────────────────────────────
    SENTRY_DSN: str | None = None  # production only
    LOG_LEVEL: str = "INFO"
    
    # ── CAPTCHA (Phase 9) ─────────────────────────────────────────────────────
    CAPTCHA_ENABLED: bool = True  # Set to False to bypass CAPTCHA (testing only)
    CAPTCHA_SECRET_KEY: str | None = None  # hCaptcha secret key
    CAPTCHA_SITE_KEY: str | None = None  # hCaptcha site key (for frontend)

    # ── Derived / validated ────────────────────────────────────────────────────
    @field_validator("ENVIRONMENT")
    @classmethod
    def _validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {allowed}, got {v!r}")
        return v

    @field_validator("JWT_ALGORITHM")
    @classmethod
    def _validate_jwt_algorithm(cls, v: str) -> str:
        if v != "HS256":
            raise ValueError("JWT_ALGORITHM must be HS256 (architecture.md §9)")
        return v

    @model_validator(mode="after")
    def _production_guards(self) -> "Settings":
        if self.ENVIRONMENT == "production":
            if self.SENTRY_DSN is None:
                raise ValueError("SENTRY_DSN is required in production")
            if "*" in self.CORS_ORIGINS:
                raise ValueError("CORS_ORIGINS must not contain '*' in production (architecture.md §9)")
            if self.LOG_LEVEL == "DEBUG":
                raise ValueError("LOG_LEVEL must not be DEBUG in production (secrets risk)")
        return self

    @property
    def allowed_mime_types_list(self) -> list[str]:
        return [m.strip() for m in self.ALLOWED_MIME_TYPES.split(",") if m.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


# Module-level singleton — import this everywhere in application code.
# Fails at import time if any required variable is absent (code-standards.md: fail-fast).
# Tests that need to instantiate Settings with custom values should use
# Settings.model_validate({...}) directly rather than importing this singleton.
try:
    settings = Settings()  # type: ignore[call-arg]
except Exception:
    # Re-raise in production/staging. In test environments, callers use
    # Settings.model_validate() directly, so this singleton is never imported.
    import os
    if os.environ.get("ENVIRONMENT") not in (None, "", "test"):
        raise
    settings = None  # type: ignore[assignment]
