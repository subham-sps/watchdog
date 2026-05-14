"""
Test infrastructure.

Strategy:
- Uses watchdog_test Postgres database (same container, separate DB).
- Alembic migrations run once per session (sync subprocess) before any test.
- Each test gets its own engine + connection + transaction on its own event
  loop (function scope). This avoids all cross-loop issues with asyncpg.
- The transaction is rolled back after every test — DB stays clean.
- join_transaction_mode="create_savepoint" lets the AsyncSession issue a
  SAVEPOINT instead of BEGIN, coexisting with the outer transaction.
  source_service uses begin_nested() which nests cleanly inside this.
"""
import os
import subprocess
import sys
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.main import app

TEST_DB_URL = settings.test_database_url


@pytest.fixture(scope="session", autouse=True)
def apply_migrations():
    """Run alembic upgrade head once before any tests."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        env={**os.environ, "DATABASE_URL": TEST_DB_URL},
    )
    assert result.returncode == 0, f"Alembic migration failed:\n{result.stderr}"


@pytest_asyncio.fixture()
async def db_session():
    """
    Creates a fresh engine for this test's event loop, begins a transaction,
    yields a session, then rolls back everything. Each test is fully isolated.
    """
    engine = create_async_engine(TEST_DB_URL, echo=False, pool_pre_ping=True)
    conn = await engine.connect()
    trans = await conn.begin()
    session = AsyncSession(
        bind=conn,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await conn.close()
        await engine.dispose()


@pytest_asyncio.fixture()
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


API_KEY = settings.api_keys[0]


@pytest.fixture()
def auth_headers():
    return {settings.api_key_header: API_KEY}
