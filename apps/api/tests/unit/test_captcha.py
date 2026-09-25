"""
Unit tests for CAPTCHA Service — Phase 9
Tests hCaptcha verification and configuration.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import httpx

from app.services.captcha import captcha_service


class TestCaptchaService:
    """Test CAPTCHA service functions."""
    
    @pytest.mark.asyncio
    @patch("app.services.captcha.settings")
    async def test_verify_captcha_disabled(self, mock_settings):
        """Test CAPTCHA verification when disabled."""
        mock_settings.CAPTCHA_ENABLED = False
        
        is_valid, error = await captcha_service.verify_captcha("dummy-token")
        
        # Should bypass verification
        assert is_valid is True
        assert error is None
    
    @pytest.mark.asyncio
    @patch("app.services.captcha.settings")
    async def test_verify_captcha_no_secret_development(self, mock_settings):
        """Test CAPTCHA verification without secret key in development."""
        mock_settings.CAPTCHA_ENABLED = True
        mock_settings.CAPTCHA_SECRET_KEY = None
        mock_settings.ENVIRONMENT = "development"
        
        is_valid, error = await captcha_service.verify_captcha("dummy-token")
        
        # Should bypass in development
        assert is_valid is True
        assert error is None
    
    @pytest.mark.asyncio
    @patch("app.services.captcha.settings")
    async def test_verify_captcha_no_secret_production(self, mock_settings):
        """Test CAPTCHA verification without secret key in production."""
        mock_settings.CAPTCHA_ENABLED = True
        mock_settings.CAPTCHA_SECRET_KEY = None
        mock_settings.ENVIRONMENT = "production"
        
        is_valid, error = await captcha_service.verify_captcha("dummy-token")
        
        # Should fail in production
        assert is_valid is False
        assert "configuration error" in error.lower()
    
    @pytest.mark.asyncio
    @patch("app.services.captcha.settings")
    @patch("app.services.captcha.httpx.AsyncClient")
    async def test_verify_captcha_success(self, mock_client_class, mock_settings):
        """Test successful CAPTCHA verification."""
        mock_settings.CAPTCHA_ENABLED = True
        mock_settings.CAPTCHA_SECRET_KEY = "test-secret"
        mock_settings.ENVIRONMENT = "production"
        
        # Mock hCaptcha API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "challenge_ts": "2024-01-15T12:00:00Z",
            "hostname": "example.com",
        }
        mock_response.raise_for_status = MagicMock()
        
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        
        mock_client_class.return_value = mock_client
        
        is_valid, error = await captcha_service.verify_captcha(
            "valid-token",
            remote_ip="1.2.3.4",
        )
        
        # Should succeed
        assert is_valid is True
        assert error is None
        
        # Verify API call
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://hcaptcha.com/siteverify"
        assert call_args[1]["data"]["secret"] == "test-secret"
        assert call_args[1]["data"]["response"] == "valid-token"
        assert call_args[1]["data"]["remoteip"] == "1.2.3.4"
    
    @pytest.mark.asyncio
    @patch("app.services.captcha.settings")
    @patch("app.services.captcha.httpx.AsyncClient")
    async def test_verify_captcha_invalid_response(self, mock_client_class, mock_settings):
        """Test CAPTCHA verification with invalid response token."""
        mock_settings.CAPTCHA_ENABLED = True
        mock_settings.CAPTCHA_SECRET_KEY = "test-secret"
        mock_settings.ENVIRONMENT = "production"
        
        # Mock hCaptcha API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": False,
            "error-codes": ["invalid-input-response"],
        }
        mock_response.raise_for_status = MagicMock()
        
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        
        mock_client_class.return_value = mock_client
        
        is_valid, error = await captcha_service.verify_captcha("invalid-token")
        
        # Should fail with user-friendly message
        assert is_valid is False
        assert "invalid or expired" in error.lower()
    
    @pytest.mark.asyncio
    @patch("app.services.captcha.settings")
    @patch("app.services.captcha.httpx.AsyncClient")
    async def test_verify_captcha_already_seen(self, mock_client_class, mock_settings):
        """Test CAPTCHA verification with already used token."""
        mock_settings.CAPTCHA_ENABLED = True
        mock_settings.CAPTCHA_SECRET_KEY = "test-secret"
        mock_settings.ENVIRONMENT = "production"
        
        # Mock hCaptcha API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": False,
            "error-codes": ["invalid-or-already-seen-response"],
        }
        mock_response.raise_for_status = MagicMock()
        
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        
        mock_client_class.return_value = mock_client
        
        is_valid, error = await captcha_service.verify_captcha("used-token")
        
        # Should fail with specific message
        assert is_valid is False
        assert "already been used" in error.lower()
    
    @pytest.mark.asyncio
    @patch("app.services.captcha.settings")
    @patch("app.services.captcha.httpx.AsyncClient")
    async def test_verify_captcha_timeout(self, mock_client_class, mock_settings):
        """Test CAPTCHA verification with timeout error."""
        mock_settings.CAPTCHA_ENABLED = True
        mock_settings.CAPTCHA_SECRET_KEY = "test-secret"
        mock_settings.ENVIRONMENT = "production"
        
        # Mock hCaptcha API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": False,
            "error-codes": ["timeout-or-duplicate"],
        }
        mock_response.raise_for_status = MagicMock()
        
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        
        mock_client_class.return_value = mock_client
        
        is_valid, error = await captcha_service.verify_captcha("timeout-token")
        
        # Should fail with timeout message
        assert is_valid is False
        assert "timed out" in error.lower()
    
    @pytest.mark.asyncio
    @patch("app.services.captcha.settings")
    @patch("app.services.captcha.httpx.AsyncClient")
    async def test_verify_captcha_http_error_development(self, mock_client_class, mock_settings):
        """Test CAPTCHA verification with HTTP error in development."""
        mock_settings.CAPTCHA_ENABLED = True
        mock_settings.CAPTCHA_SECRET_KEY = "test-secret"
        mock_settings.ENVIRONMENT = "development"
        
        # Mock HTTP error
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.HTTPError("Connection failed")
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        
        mock_client_class.return_value = mock_client
        
        is_valid, error = await captcha_service.verify_captcha("any-token")
        
        # Should bypass in development
        assert is_valid is True
        assert error is None
    
    @pytest.mark.asyncio
    @patch("app.services.captcha.settings")
    @patch("app.services.captcha.httpx.AsyncClient")
    async def test_verify_captcha_http_error_production(self, mock_client_class, mock_settings):
        """Test CAPTCHA verification with HTTP error in production."""
        mock_settings.CAPTCHA_ENABLED = True
        mock_settings.CAPTCHA_SECRET_KEY = "test-secret"
        mock_settings.ENVIRONMENT = "production"
        
        # Mock HTTP error
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.HTTPError("Connection failed")
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        
        mock_client_class.return_value = mock_client
        
        is_valid, error = await captcha_service.verify_captcha("any-token")
        
        # Should fail in production
        assert is_valid is False
        assert "unavailable" in error.lower()
    
    @pytest.mark.asyncio
    @patch("app.services.captcha.settings")
    @patch("app.services.captcha.httpx.AsyncClient")
    async def test_verify_captcha_unexpected_error_development(self, mock_client_class, mock_settings):
        """Test CAPTCHA verification with unexpected error in development."""
        mock_settings.CAPTCHA_ENABLED = True
        mock_settings.CAPTCHA_SECRET_KEY = "test-secret"
        mock_settings.ENVIRONMENT = "development"
        
        # Mock unexpected error
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Unexpected error")
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        
        mock_client_class.return_value = mock_client
        
        is_valid, error = await captcha_service.verify_captcha("any-token")
        
        # Should bypass in development
        assert is_valid is True
        assert error is None
    
    @pytest.mark.asyncio
    @patch("app.services.captcha.settings")
    @patch("app.services.captcha.httpx.AsyncClient")
    async def test_verify_captcha_unexpected_error_production(self, mock_client_class, mock_settings):
        """Test CAPTCHA verification with unexpected error in production."""
        mock_settings.CAPTCHA_ENABLED = True
        mock_settings.CAPTCHA_SECRET_KEY = "test-secret"
        mock_settings.ENVIRONMENT = "production"
        
        # Mock unexpected error
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Unexpected error")
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = AsyncMock()
        
        mock_client_class.return_value = mock_client
        
        is_valid, error = await captcha_service.verify_captcha("any-token")
        
        # Should fail in production
        assert is_valid is False
        assert "error" in error.lower()
    
    @patch("app.services.captcha.settings")
    def test_is_enabled_true(self, mock_settings):
        """Test CAPTCHA enabled check when enabled."""
        mock_settings.CAPTCHA_ENABLED = True
        mock_settings.CAPTCHA_SECRET_KEY = "test-secret"
        
        assert captcha_service.is_enabled() is True
    
    @patch("app.services.captcha.settings")
    def test_is_enabled_disabled(self, mock_settings):
        """Test CAPTCHA enabled check when disabled."""
        mock_settings.CAPTCHA_ENABLED = False
        mock_settings.CAPTCHA_SECRET_KEY = "test-secret"
        
        assert captcha_service.is_enabled() is False
    
    @patch("app.services.captcha.settings")
    def test_is_enabled_no_secret(self, mock_settings):
        """Test CAPTCHA enabled check without secret key."""
        mock_settings.CAPTCHA_ENABLED = True
        mock_settings.CAPTCHA_SECRET_KEY = None
        
        assert captcha_service.is_enabled() is False
