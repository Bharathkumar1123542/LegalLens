"""
Rate limiting — LegalLens Phase 8
Implements: architecture.md §10 Mitigation Strategies (rate limiting)
Uses slowapi with Redis backend to prevent abuse and DDoS attacks.
"""

import logging
from typing import Callable

from fastapi import Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_identifier(request: Request) -> str:
    """
    Get rate limit identifier (IP or user ID).
    
    Per architecture.md §10: Use authenticated user ID when available,
    fall back to IP address for unauthenticated requests.
    """
    # Try to get user ID from request state (set by auth dependency)
    if hasattr(request.state, "user_id") and request.state.user_id:
        identifier = f"user:{request.state.user_id}"
        logger.debug(f"Rate limit identifier: {identifier}")
        return identifier
    
    # Fall back to IP address
    ip_address = get_remote_address(request)
    identifier = f"ip:{ip_address}"
    logger.debug(f"Rate limit identifier: {identifier}")
    return identifier


# Initialize rate limiter with Redis backend
limiter = Limiter(
    key_func=get_identifier,
    storage_uri=settings.REDIS_URL,
    strategy="fixed-window",
    headers_enabled=True,  # Add rate limit headers to responses
    swallow_errors=True,    # Don't crash if Redis is down
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """
    Custom handler for rate limit exceeded errors.
    
    Returns 429 Too Many Requests with helpful message.
    """
    logger.warning(
        f"Rate limit exceeded: path={request.url.path}, "
        f"identifier={get_identifier(request)}"
    )
    
    return Response(
        content={
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please try again later.",
            "retry_after": exc.detail,
        },
        status_code=429,
        headers={
            "Retry-After": str(exc.detail),
            "X-RateLimit-Limit": str(exc.limit),
            "X-RateLimit-Remaining": "0",
        },
    )


# Rate limit configurations per endpoint category
class RateLimits:
    """
    Rate limit definitions per architecture.md §10.
    
    Categories:
    - Auth: Strict limits to prevent brute force
    - Upload: Moderate limits to prevent storage abuse
    - LLM: Tight limits to control API costs
    - Read: Generous limits for normal usage
    """
    
    # Authentication endpoints (prevent brute force)
    AUTH_REGISTER = "5/minute"    # 5 registrations per minute
    AUTH_LOGIN = "10/minute"       # 10 login attempts per minute
    AUTH_REFRESH = "20/minute"     # 20 token refreshes per minute
    
    # Upload endpoints (prevent storage abuse)
    DOCUMENT_UPLOAD = "10/hour"    # 10 document uploads per hour
    
    # LLM-powered endpoints (control API costs)
    SIMPLIFY = "30/hour"           # 30 simplifications per hour
    EXTRACT_CLAUSES = "30/hour"    # 30 extractions per hour
    CHAT = "60/hour"               # 60 chat messages per hour
    COMPARE = "20/hour"            # 20 comparisons per hour
    
    # Export endpoints (moderate limits)
    CREATE_EXPORT = "50/hour"      # 50 export creations per hour
    
    # Read endpoints (generous limits)
    READ_OPS = "200/minute"        # 200 reads per minute (list, get, etc.)
    
    # Health check (no limit)
    HEALTH = "1000/minute"         # Very high limit for monitoring


def get_rate_limit_for_endpoint(path: str, method: str) -> str:
    """
    Get rate limit for a specific endpoint.
    
    Args:
        path: Request path (e.g., "/api/v1/auth/login")
        method: HTTP method (GET, POST, etc.)
    
    Returns:
        Rate limit string (e.g., "10/minute")
    """
    # Auth endpoints
    if "/auth/register" in path:
        return RateLimits.AUTH_REGISTER
    if "/auth/login" in path:
        return RateLimits.AUTH_LOGIN
    if "/auth/refresh" in path:
        return RateLimits.AUTH_REFRESH
    
    # Upload endpoints
    if "/documents/upload" in path:
        return RateLimits.DOCUMENT_UPLOAD
    
    # LLM endpoints
    if "/simplify" in path:
        return RateLimits.SIMPLIFY
    if "/extract-clauses" in path:
        return RateLimits.EXTRACT_CLAUSES
    if "/chat/" in path and method == "POST":
        return RateLimits.CHAT
    if "/comparisons" in path and method == "POST":
        return RateLimits.COMPARE
    
    # Export endpoints
    if "/exports" in path and method == "POST":
        return RateLimits.CREATE_EXPORT
    
    # Health check
    if path == "/health":
        return RateLimits.HEALTH
    
    # Default for read operations
    if method == "GET":
        return RateLimits.READ_OPS
    
    # Default fallback (conservative)
    return "100/minute"


def log_rate_limit_info(request: Request) -> None:
    """
    Log rate limit information for monitoring.
    
    Logs remaining requests and reset time.
    """
    # Extract rate limit headers if present
    headers = getattr(request.state, "_rate_limit_headers", {})
    
    if headers:
        logger.info(
            f"Rate limit status: path={request.url.path}, "
            f"limit={headers.get('X-RateLimit-Limit')}, "
            f"remaining={headers.get('X-RateLimit-Remaining')}, "
            f"reset={headers.get('X-RateLimit-Reset')}"
        )
