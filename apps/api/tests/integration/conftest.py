"""
Integration test fixtures — LegalLens API
Provides: async test DB, FastAPI TestClient, auth fixtures.
"""

import asyncio
import uuid
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import hash_password, create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.models.document import Document


# ── Test database setup ───────────────────────────────────────────────────────
# Use in-memory SQLite for fast integration tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Create a fresh database for each test.
    Tables are created before the test and dropped after.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestSessionLocal() as session:
        yield session
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def test_client(db_session: AsyncSession) -> Generator:
    """
    FastAPI TestClient with overridden DB dependency.
    Synchronous client for simple request/response tests.
    """
    def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession) -> AsyncGenerator:
    """
    Async HTTP client for streaming response tests.
    """
    def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


# ── Auth fixtures ─────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user with a known password."""
    user = User(
        id=uuid.uuid4(),
        email="testuser@example.com",
        password_hash=hash_password("TestPassword123!"),
        full_name="Test User",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def another_user(db_session: AsyncSession) -> User:
    """Create a second user for ownership enforcement tests."""
    user = User(
        id=uuid.uuid4(),
        email="otheruser@example.com",
        password_hash=hash_password("OtherPassword123!"),
        full_name="Other User",
        role="user",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict[str, str]:
    """Generate Authorization header for the test user."""
    token = create_access_token(str(test_user.id), test_user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_auth_headers(another_user: User) -> dict[str, str]:
    """Generate Authorization header for the second user."""
    token = create_access_token(str(another_user.id), another_user.email)
    return {"Authorization": f"Bearer {token}"}


# ── Document fixtures ─────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def test_document(db_session: AsyncSession, test_user: User) -> Document:
    """Create a test document owned by test_user."""
    doc = Document(
        id=uuid.uuid4(),
        owner_id=test_user.id,
        original_filename="test.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        storage_key=f"{test_user.id}/test-doc-id/test.pdf",
        file_hash_sha256="a" * 64,
        status="ready",
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    return doc
