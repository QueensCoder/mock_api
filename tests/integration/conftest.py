"""Integration-only fixtures — requires a running postgres and redis."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.auth import get_stytch_client
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from tests.conftest import make_stytch_client, make_stytch_response

TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/app_test"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(bind=test_engine, expire_on_commit=False)


@pytest.fixture(scope="session", autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncSession:
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncClient:
    """Unauthenticated test client."""
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def authed_client(db_session: AsyncSession) -> AsyncClient:
    """Test client with a valid Stytch session pre-wired."""
    stytch_mock = make_stytch_client(response=make_stytch_response())
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_stytch_client] = lambda: stytch_mock
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": "Bearer valid-session-token"},
    ) as c:
        yield c
    app.dependency_overrides.clear()
