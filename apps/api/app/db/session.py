"""
SQLAlchemy async session factory — LegalLens
Implements: architecture.md §4 (PostgreSQL + asyncpg), code-standards.md (parameterized queries only, ORM).
Engine is created lazily so that test overrides (conftest.py) can replace get_db
before any real database connection is attempted.
"""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

_engine = None
_AsyncSessionLocal = None


def _get_engine():
    global _engine, _AsyncSessionLocal
    if _engine is None:
        _engine = create_async_engine(
            settings.DATABASE_URL,
            # Connection pool: mitigates DB connection exhaustion (architecture.md §10)
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=settings.ENVIRONMENT == "development",
        )
        _AsyncSessionLocal = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _engine, _AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency — yields a request-scoped async session.
    In tests, this function is replaced via app.dependency_overrides[get_db].
    """
    _, session_factory = _get_engine()
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


def get_async_session():
    """
    Context manager for standalone async sessions (used by Celery workers).
    Returns an async context manager that yields an AsyncSession.
    """
    _, session_factory = _get_engine()
    return session_factory()
