"""
Unit tests for core/config.py
Implements: code-standards.md §Testing Strategy (unit), architecture.md §9
Tests:
  - Valid config instantiates without error
  - Missing required variable raises ValidationError at instantiation
  - Invalid ENVIRONMENT value raises ValidationError
  - Production guards: SENTRY_DSN required, CORS '*' rejected, DEBUG rejected
  - Derived properties parse correctly
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError


def _make_settings(**overrides):
    """Helper: build a Settings from a known-good base dict, then apply overrides."""
    # pytest runs from apps/api/, so the import path is app.core.config
    from app.core.config import Settings

    base = {
        "ENVIRONMENT": "development",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/legallens",
        "REDIS_URL": "redis://localhost:6379/0",
        "CELERY_BROKER_URL": "redis://localhost:6379/1",
        "S3_BUCKET": "legallens-dev",
        "S3_ACCESS_KEY_ID": "minioadmin",
        "S3_SECRET_ACCESS_KEY": "minioadmin",
        "ANTHROPIC_API_KEY": "sk-ant-test",
        "VOYAGE_API_KEY": "pa-test",
        "JWT_SECRET": "a" * 32,
        "CORS_ORIGINS": "http://localhost:3000",
        "LOG_LEVEL": "INFO",
    }
    base.update(overrides)
    return Settings.model_validate(base)


class TestSettingsValidInstantiation:
    def test_valid_config_instantiates(self):
        s = _make_settings()
        assert s.ENVIRONMENT == "development"
        assert s.ACCESS_TOKEN_EXPIRE_MINUTES == 15
        assert s.REFRESH_TOKEN_EXPIRE_DAYS == 14
        assert s.MAX_UPLOAD_SIZE_MB == 20

    def test_derived_max_upload_bytes(self):
        s = _make_settings(MAX_UPLOAD_SIZE_MB=20)
        assert s.max_upload_size_bytes == 20 * 1024 * 1024

    def test_derived_mime_types_list(self):
        s = _make_settings()
        mime = s.allowed_mime_types_list
        assert "application/pdf" in mime
        assert len(mime) == 3

    def test_derived_cors_list(self):
        s = _make_settings(CORS_ORIGINS="http://localhost:3000,https://app.legallens.io")
        origins = s.cors_origins_list
        assert len(origins) == 2
        assert "http://localhost:3000" in origins


class TestSettingsMissingRequired:
    @pytest.mark.parametrize("missing_field", [
        "DATABASE_URL",
        "REDIS_URL",
        "CELERY_BROKER_URL",
        "S3_BUCKET",
        "S3_ACCESS_KEY_ID",
        "S3_SECRET_ACCESS_KEY",
        "ANTHROPIC_API_KEY",
        "VOYAGE_API_KEY",
        "JWT_SECRET",
        "CORS_ORIGINS",
        "ENVIRONMENT",
    ])
    def test_missing_required_raises(self, missing_field, monkeypatch):
        """
        Validates that Settings raises when a required field is absent.
        Uses an IsolatedSettings subclass with env_file=None so .env.test
        doesn't silently supply the "missing" field.
        """
        base = {
            "ENVIRONMENT": "development",
            "DATABASE_URL": "postgresql+asyncpg://u:p@localhost/db",
            "REDIS_URL": "redis://localhost:6379/0",
            "CELERY_BROKER_URL": "redis://localhost:6379/1",
            "S3_BUCKET": "bucket",
            "S3_ACCESS_KEY_ID": "key",
            "S3_SECRET_ACCESS_KEY": "secret",
            "ANTHROPIC_API_KEY": "sk",
            "VOYAGE_API_KEY": "pk",
            "JWT_SECRET": "x" * 32,
            "CORS_ORIGINS": "http://localhost:3000",
        }
        base.pop(missing_field, None)
        monkeypatch.delenv(missing_field, raising=False)

        from app.core.config import Settings
        from pydantic_settings import SettingsConfigDict

        class IsolatedSettings(Settings):
            model_config = SettingsConfigDict(
                env_file=None,
                case_sensitive=True,
                extra="ignore",
            )

        with pytest.raises(ValidationError):
            IsolatedSettings.model_validate(base)



class TestSettingsValidation:
    def test_invalid_environment_raises(self):
        with pytest.raises(ValidationError, match="ENVIRONMENT must be one of"):
            _make_settings(ENVIRONMENT="test_env")

    def test_invalid_jwt_algorithm_raises(self):
        with pytest.raises(ValidationError, match="JWT_ALGORITHM must be HS256"):
            _make_settings(JWT_ALGORITHM="RS256")

    def test_staging_environment_allowed(self):
        s = _make_settings(ENVIRONMENT="staging")
        assert s.ENVIRONMENT == "staging"

    def test_production_environment_allowed(self):
        # production requires SENTRY_DSN
        s = _make_settings(
            ENVIRONMENT="production",
            SENTRY_DSN="https://sentry.io/test",
            LOG_LEVEL="INFO",
        )
        assert s.ENVIRONMENT == "production"


class TestProductionGuards:
    def test_production_without_sentry_raises(self):
        with pytest.raises(ValidationError, match="SENTRY_DSN is required in production"):
            _make_settings(ENVIRONMENT="production", SENTRY_DSN=None)

    def test_production_cors_wildcard_raises(self):
        with pytest.raises(ValidationError, match="must not contain"):
            _make_settings(
                ENVIRONMENT="production",
                SENTRY_DSN="https://sentry.io/test",
                CORS_ORIGINS="*",
            )

    def test_production_debug_log_level_raises(self):
        with pytest.raises(ValidationError, match="LOG_LEVEL must not be DEBUG"):
            _make_settings(
                ENVIRONMENT="production",
                SENTRY_DSN="https://sentry.io/test",
                CORS_ORIGINS="https://app.legallens.io",
                LOG_LEVEL="DEBUG",
            )

    def test_development_allows_no_sentry(self):
        """Development env must NOT require SENTRY_DSN."""
        s = _make_settings(ENVIRONMENT="development", SENTRY_DSN=None)
        assert s.SENTRY_DSN is None

    def test_development_allows_debug(self):
        s = _make_settings(ENVIRONMENT="development", LOG_LEVEL="DEBUG")
        assert s.LOG_LEVEL == "DEBUG"
