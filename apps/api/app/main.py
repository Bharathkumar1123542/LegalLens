"""
LegalLens API — FastAPI application entry point.
Implements: architecture.md §1 (API Gateway/BFF), Phase 0 exit criteria (GET /health → 200).
Middleware: CORS (never '*' in prod), structured logging, Sentry.
code-standards.md: config loaded from Settings (fail-fast on missing vars).
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.rate_limiter import limiter, rate_limit_exceeded_handler

# ── Logging — configure before any other imports that log ─────────────────────
configure_logging(
    log_level=settings.LOG_LEVEL,
    json_output=settings.ENVIRONMENT != "development",
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle."""
    logger.info(
        "legallens_api_starting",
        environment=settings.ENVIRONMENT,
        log_level=settings.LOG_LEVEL,
    )
    yield
    logger.info("legallens_api_shutdown")


# ── Optional Sentry integration ───────────────────────────────────────────────
if settings.SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        environment=settings.ENVIRONMENT,
        # Never send raw request bodies (may contain PII / document content)
        send_default_pii=False,
    )


# ── Application factory ───────────────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title="LegalLens API",
        version="0.1.0",
        docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )
    
    # ── Rate limiting (Phase 8) ───────────────────────────────────────────────
    from slowapi.errors import RateLimitExceeded
    
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    
    logger.info(
        "rate_limiter_initialized",
        storage=settings.REDIS_URL,
        strategy="fixed-window",
    )

    # CORS — never wildcard in prod (architecture.md §9, code-standards.md security)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # ── Request-level structured logging ──────────────────────────────────────
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
            # Never log Authorization header (code-standards.md: secrets never logged)
        )
        return response

    # ── Health check endpoints (Phase 0, enhanced Phase 8) ────────────────────
    @app.get("/health", tags=["meta"], summary="Liveness check")
    async def health() -> dict:
        """Basic liveness probe for load balancers."""
        return {"status": "ok", "environment": settings.ENVIRONMENT}
    
    @app.get("/health/ready", tags=["meta"], summary="Readiness check")
    async def readiness() -> dict:
        """
        Readiness probe — checks dependencies.
        Returns 503 if any critical service is unavailable.
        """
        from app.db.session import async_session_maker
        from sqlalchemy import text
        
        checks = {
            "database": "unknown",
            "redis": "unknown",
            "storage": "unknown",
        }
        
        # Database check
        try:
            async with async_session_maker() as session:
                await session.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as e:
            logger.error("readiness_check_database_failed", error=str(e))
            checks["database"] = "unavailable"
        
        # Redis check (rate limiting)
        try:
            import redis.asyncio as aioredis
            redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            await redis_client.ping()
            await redis_client.close()
            checks["redis"] = "ok"
        except Exception as e:
            logger.error("readiness_check_redis_failed", error=str(e))
            checks["redis"] = "unavailable"
        
        # Storage check (S3/GCS)
        try:
            from app.services.storage import storage_service
            # Basic connectivity check - list bucket (limit 1)
            await storage_service.health_check()
            checks["storage"] = "ok"
        except Exception as e:
            logger.error("readiness_check_storage_failed", error=str(e))
            checks["storage"] = "unavailable"
        
        # Determine overall status
        all_ok = all(status == "ok" for status in checks.values())
        status_code = 200 if all_ok else 503
        
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "ready" if all_ok else "not_ready",
                "checks": checks,
                "environment": settings.ENVIRONMENT,
            }
        )
    
    @app.get("/metrics", tags=["meta"], summary="Prometheus metrics")
    async def metrics() -> dict:
        """
        Prometheus-compatible metrics endpoint.
        Returns application metrics in structured format.
        """
        from app.db.session import async_session_maker
        from sqlalchemy import text
        
        metrics_data = {
            "process_info": {
                "environment": settings.ENVIRONMENT,
                "version": "0.1.0",
            },
            "database": {},
            "application": {},
        }
        
        # Database connection pool metrics
        try:
            async with async_session_maker() as session:
                result = await session.execute(text("""
                    SELECT 
                        COUNT(*) as total_connections,
                        COUNT(*) FILTER (WHERE state = 'active') as active_connections
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                """))
                row = result.first()
                if row:
                    metrics_data["database"]["total_connections"] = row[0]
                    metrics_data["database"]["active_connections"] = row[1]
        except Exception as e:
            logger.error("metrics_database_query_failed", error=str(e))
        
        # Application metrics (would be enhanced with prometheus_client)
        try:
            async with async_session_maker() as session:
                # Document count
                result = await session.execute(text("SELECT COUNT(*) FROM documents"))
                metrics_data["application"]["total_documents"] = result.scalar()
                
                # User count
                result = await session.execute(text("SELECT COUNT(*) FROM users"))
                metrics_data["application"]["total_users"] = result.scalar()
                
                # Chat sessions count
                result = await session.execute(text("SELECT COUNT(*) FROM chat_sessions"))
                metrics_data["application"]["total_chat_sessions"] = result.scalar()
        except Exception as e:
            logger.error("metrics_application_query_failed", error=str(e))
        
        return metrics_data

    # ── API v1 routers — registered as they are implemented phase by phase ─────
    from app.api.v1 import auth, documents, chat, comparisons, exports, mfa  # Phases 1, 4, 5, 9

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(mfa.router, prefix="/api/v1")  # Phase 9: /auth/mfa/* endpoints
    app.include_router(documents.router, prefix="/api/v1")
    app.include_router(chat.router, prefix="/api/v1")  # Phase 4: /chat/sessions endpoints
    app.include_router(chat.documents_router, prefix="/api/v1")  # Phase 4: /documents/{id}/chat endpoints
    app.include_router(comparisons.router, prefix="/api/v1")  # Phase 5: /comparisons endpoints
    app.include_router(exports.router, prefix="/api/v1")  # Phase 5: /exports endpoints

    return app


app = create_app()
