"""
Test configuration and fixtures.
Uses SQLite in-memory (via aiosqlite) so tests run without Postgres.
"""

# ── MUST be first — set env before any app module is imported ────────
import os
os.environ["APP_ENV"] = "test"
os.environ["CORS_ORIGINS"] = "*"          # avoid production CORS validator
os.environ["APP_SECRET_KEY"] = "test-secret-key-exactly-32-chars!!"
os.environ["WEBHOOK_SECRET"] = "test-webhook-secret-exactly-20ch"

# Bust the lru_cache so Settings re-reads the env vars we just set
from app.config import get_settings  # noqa: E402
get_settings.cache_clear()

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import create_app
from app.models.api_key import ApiKey
from app.auth import generate_api_key

# ── SQLite in-memory engine ──────────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Pre-generated test keys
TEST_RAW_KEY_PROD, TEST_KEY_HASH_PROD = generate_api_key("usk_prod_")
TEST_RAW_KEY_FREE, TEST_KEY_HASH_FREE = generate_api_key("usk_prod_")
TEST_RAW_KEY_RO,   TEST_KEY_HASH_RO   = generate_api_key("usk_ro_")
TEST_ORG_ID = "org_test_abc123"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    """Create all tables once per test session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Individual DB session per test — rolled back after each test."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def seeded_db(db_session: AsyncSession) -> AsyncSession:
    """Session with a pro-plan API key seeded."""
    key = ApiKey(
        id="key_" + TEST_RAW_KEY_PROD[-8:],
        org_id=TEST_ORG_ID,
        name="Test Pro Key",
        key_hash=TEST_KEY_HASH_PROD,
        key_prefix=TEST_RAW_KEY_PROD[:12],
        plan="pro",
        is_active=True,
        scopes="read write",
    )
    db_session.add(key)
    await db_session.flush()
    return db_session


@pytest_asyncio.fixture
async def client(seeded_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """HTTP test client with DB override and pro API key."""
    app = create_app()

    async def override_get_db():
        yield seeded_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


@pytest_asyncio.fixture
async def authed_client(client: AsyncClient) -> AsyncClient:
    """Client pre-configured with Authorization header."""
    client.headers.update({"Authorization": f"Bearer {TEST_RAW_KEY_PROD}"})
    return client
