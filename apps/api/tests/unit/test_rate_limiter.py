"""
Unit tests — Rate limiter
Tests: Rate limit configuration, identifier extraction, limit enforcement
Covers: app/core/rate_limiter.py (Phase 8)
"""

from unittest.mock import MagicMock

import pytest
from fastapi import Request

from app.core.rate_limiter import (
    get_identifier,
    get_rate_limit_for_endpoint,
    RateLimits,
)


class TestGetIdentifier:
    """Test rate limit identifier extraction."""

    def test_authenticated_user_identifier(self):
        """Use user ID for authenticated requests."""
        request = MagicMock(spec=Request)
        request.state.user_id = "user-123"
        
        identifier = get_identifier(request)
        
        assert identifier == "user:user-123"
    
    def test_unauthenticated_ip_identifier(self):
        """Use IP address for unauthenticated requests."""
        request = MagicMock(spec=Request)
        request.state = MagicMock()
        request.state.user_id = None
        request.client.host = "192.168.1.1"
        
        identifier = get_identifier(request)
        
        assert identifier == "ip:192.168.1.1"
    
    def test_no_user_id_attribute(self):
        """Handle requests without user_id attribute."""
        request = MagicMock(spec=Request)
        del request.state.user_id  # Simulate missing attribute
        request.client.host = "10.0.0.1"
        
        identifier = get_identifier(request)
        
        assert identifier == "ip:10.0.0.1"


class TestRateLimitConfiguration:
    """Test rate limit configurations for different endpoints."""

    def test_auth_register_limit(self):
        """Register endpoint has strict limit."""
        limit = get_rate_limit_for_endpoint("/api/v1/auth/register", "POST")
        assert limit == RateLimits.AUTH_REGISTER
        assert limit == "5/minute"
    
    def test_auth_login_limit(self):
        """Login endpoint has moderate limit."""
        limit = get_rate_limit_for_endpoint("/api/v1/auth/login", "POST")
        assert limit == RateLimits.AUTH_LOGIN
        assert limit == "10/minute"
    
    def test_auth_refresh_limit(self):
        """Refresh endpoint has higher limit."""
        limit = get_rate_limit_for_endpoint("/api/v1/auth/refresh", "POST")
        assert limit == RateLimits.AUTH_REFRESH
        assert limit == "20/minute"
    
    def test_document_upload_limit(self):
        """Upload endpoint has hourly limit."""
        limit = get_rate_limit_for_endpoint("/api/v1/documents/upload", "POST")
        assert limit == RateLimits.DOCUMENT_UPLOAD
        assert limit == "10/hour"
    
    def test_simplify_limit(self):
        """Simplify endpoint (LLM) has tight limit."""
        limit = get_rate_limit_for_endpoint("/api/v1/documents/123/simplify", "POST")
        assert limit == RateLimits.SIMPLIFY
        assert limit == "30/hour"
    
    def test_extract_clauses_limit(self):
        """Extract clauses endpoint (LLM) has tight limit."""
        limit = get_rate_limit_for_endpoint("/api/v1/documents/123/extract-clauses", "POST")
        assert limit == RateLimits.EXTRACT_CLAUSES
        assert limit == "30/hour"
    
    def test_chat_limit(self):
        """Chat endpoint (LLM) has moderate limit."""
        limit = get_rate_limit_for_endpoint("/api/v1/chat/session-123", "POST")
        assert limit == RateLimits.CHAT
        assert limit == "60/hour"
    
    def test_compare_limit(self):
        """Compare endpoint (LLM) has tight limit."""
        limit = get_rate_limit_for_endpoint("/api/v1/comparisons", "POST")
        assert limit == RateLimits.COMPARE
        assert limit == "20/hour"
    
    def test_create_export_limit(self):
        """Export creation has moderate limit."""
        limit = get_rate_limit_for_endpoint("/api/v1/exports", "POST")
        assert limit == RateLimits.CREATE_EXPORT
        assert limit == "50/hour"
    
    def test_read_operations_limit(self):
        """Read operations have generous limits."""
        limit = get_rate_limit_for_endpoint("/api/v1/documents", "GET")
        assert limit == RateLimits.READ_OPS
        assert limit == "200/minute"
        
        limit = get_rate_limit_for_endpoint("/api/v1/documents/123", "GET")
        assert limit == RateLimits.READ_OPS
    
    def test_health_check_limit(self):
        """Health check has very high limit."""
        limit = get_rate_limit_for_endpoint("/health", "GET")
        assert limit == RateLimits.HEALTH
        assert limit == "1000/minute"
    
    def test_fallback_limit(self):
        """Unknown endpoints get conservative default."""
        limit = get_rate_limit_for_endpoint("/api/v1/unknown", "POST")
        assert limit == "100/minute"


class TestRateLimitValues:
    """Test rate limit value definitions."""

    def test_all_limits_defined(self):
        """All limit categories have values."""
        assert RateLimits.AUTH_REGISTER
        assert RateLimits.AUTH_LOGIN
        assert RateLimits.AUTH_REFRESH
        assert RateLimits.DOCUMENT_UPLOAD
        assert RateLimits.SIMPLIFY
        assert RateLimits.EXTRACT_CLAUSES
        assert RateLimits.CHAT
        assert RateLimits.COMPARE
        assert RateLimits.CREATE_EXPORT
        assert RateLimits.READ_OPS
        assert RateLimits.HEALTH
    
    def test_limit_format_valid(self):
        """All limits follow 'number/unit' format."""
        limits = [
            RateLimits.AUTH_REGISTER,
            RateLimits.AUTH_LOGIN,
            RateLimits.DOCUMENT_UPLOAD,
            RateLimits.SIMPLIFY,
            RateLimits.CHAT,
            RateLimits.READ_OPS,
        ]
        
        for limit in limits:
            assert "/" in limit
            number, unit = limit.split("/")
            assert number.isdigit()
            assert unit in ["second", "minute", "hour", "day"]
    
    def test_auth_limits_strictest(self):
        """Auth endpoints have strictest limits (prevent brute force)."""
        register_num = int(RateLimits.AUTH_REGISTER.split("/")[0])
        login_num = int(RateLimits.AUTH_LOGIN.split("/")[0])
        
        # Register should be more restrictive than login
        assert register_num <= login_num
        
        # Both should be in requests per minute (not hour)
        assert "minute" in RateLimits.AUTH_REGISTER
        assert "minute" in RateLimits.AUTH_LOGIN
    
    def test_llm_limits_control_costs(self):
        """LLM endpoints have hourly limits to control API costs."""
        assert "hour" in RateLimits.SIMPLIFY
        assert "hour" in RateLimits.EXTRACT_CLAUSES
        assert "hour" in RateLimits.CHAT
        assert "hour" in RateLimits.COMPARE
    
    def test_read_ops_most_generous(self):
        """Read operations have most generous limits."""
        read_num = int(RateLimits.READ_OPS.split("/")[0])
        auth_num = int(RateLimits.AUTH_LOGIN.split("/")[0])
        
        # Read ops should allow more requests
        assert read_num > auth_num * 10
