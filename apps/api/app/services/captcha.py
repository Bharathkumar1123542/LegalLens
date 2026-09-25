"""
CAPTCHA Service — Phase 9
hCaptcha integration for bot prevention.

Features:
- hCaptcha verification (privacy-focused alternative to reCAPTCHA)
- Configurable bypass for testing
- Rate limiting backup (if CAPTCHA bypassed)
- Error handling for verification failures

Configuration:
- CAPTCHA_ENABLED: Enable/disable CAPTCHA (default: True in production)
- CAPTCHA_SECRET_KEY: hCaptcha secret key
- CAPTCHA_SITE_KEY: hCaptcha site key (for frontend)

Usage:
1. Frontend includes hCaptcha widget
2. User completes CAPTCHA challenge
3. Frontend sends response token to API
4. API verifies token with hCaptcha API
5. If valid, allow registration
"""

from __future__ import annotations

from typing import Optional

import httpx
import structlog

from app.core.config import settings

log = structlog.get_logger(__name__)

HCAPTCHA_VERIFY_URL = "https://hcaptcha.com/siteverify"


class CaptchaService:
    """Service for CAPTCHA verification."""
    
    @staticmethod
    async def verify_captcha(
        response_token: str,
        remote_ip: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Verify hCaptcha response token.
        
        Args:
            response_token: hCaptcha response token from frontend
            remote_ip: User's IP address (optional, for additional validation)
        
        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if CAPTCHA verified successfully
            - error_message: Error message if verification failed, None otherwise
        
        Error Codes (from hCaptcha):
        - missing-input-secret: Secret key is missing
        - invalid-input-secret: Secret key is invalid
        - missing-input-response: Response token is missing
        - invalid-input-response: Response token is invalid or expired
        - bad-request: Request is malformed
        - invalid-or-already-seen-response: Token has already been used
        - sitekey-secret-mismatch: Site key doesn't match secret key
        """
        # Check if CAPTCHA is enabled
        if not getattr(settings, "CAPTCHA_ENABLED", True):
            log.info("captcha_verification_bypassed", reason="disabled_in_config")
            return True, None
        
        # Check if secret key is configured
        captcha_secret = getattr(settings, "CAPTCHA_SECRET_KEY", None)
        if not captcha_secret:
            log.warning("captcha_verification_failed", reason="secret_key_not_configured")
            # In development: allow bypass
            # In production: should fail
            if settings.ENVIRONMENT == "development":
                return True, None
            return False, "CAPTCHA configuration error"
        
        # Prepare verification request
        data = {
            "secret": captcha_secret,
            "response": response_token,
        }
        
        if remote_ip:
            data["remoteip"] = remote_ip
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    HCAPTCHA_VERIFY_URL,
                    data=data,
                    timeout=10.0,
                )
                response.raise_for_status()
                result = response.json()
            
            success = result.get("success", False)
            error_codes = result.get("error-codes", [])
            
            if success:
                log.info("captcha_verification_success")
                return True, None
            
            # Verification failed
            error_message = f"CAPTCHA verification failed: {', '.join(error_codes)}"
            log.warning(
                "captcha_verification_failed",
                error_codes=error_codes,
                hostname=result.get("hostname"),
            )
            
            # User-friendly error messages
            if "invalid-input-response" in error_codes:
                return False, "CAPTCHA response is invalid or expired. Please try again."
            elif "invalid-or-already-seen-response" in error_codes:
                return False, "CAPTCHA response has already been used. Please complete the challenge again."
            elif "timeout-or-duplicate" in error_codes:
                return False, "CAPTCHA verification timed out. Please try again."
            else:
                return False, "CAPTCHA verification failed. Please try again."
        
        except httpx.HTTPError as e:
            log.error("captcha_verification_http_error", error=str(e))
            # In case of network errors, allow bypass in development
            if settings.ENVIRONMENT == "development":
                return True, None
            return False, "CAPTCHA verification service unavailable. Please try again later."
        
        except Exception as e:
            log.error("captcha_verification_unexpected_error", error=str(e))
            # In case of unexpected errors, allow bypass in development
            if settings.ENVIRONMENT == "development":
                return True, None
            return False, "CAPTCHA verification error. Please try again."
    
    @staticmethod
    def is_enabled() -> bool:
        """
        Check if CAPTCHA is enabled in current environment.
        
        Returns:
            True if CAPTCHA is enabled and configured
        """
        captcha_enabled = getattr(settings, "CAPTCHA_ENABLED", True)
        captcha_secret = getattr(settings, "CAPTCHA_SECRET_KEY", None)
        
        return captcha_enabled and bool(captcha_secret)


# Singleton instance
captcha_service = CaptchaService()
