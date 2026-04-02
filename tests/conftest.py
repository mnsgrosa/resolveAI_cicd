import hashlib
import uuid

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_session
from app.main import app
from app.models.pattern import ApiKey, Base

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
TEST_API_KEY = "test-api-key-12345"
TEST_REPO = "test-owner/test-repo"

engine = create_async_engine(TEST_DB_URL)
TestSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def override_get_session():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_session] = override_get_session


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed a test API key
    async with TestSessionLocal() as session:
        key_hash = hashlib.sha256(TEST_API_KEY.encode()).hexdigest()
        api_key = ApiKey(
            id=str(uuid.uuid4()),
            key_hash=key_hash,
            repository=TEST_REPO,
            is_active=True,
        )
        session.add(api_key)
        await session.commit()

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
