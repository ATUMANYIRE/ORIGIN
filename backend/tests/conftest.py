"""Pytest fixtures for ORIGIN backend unit and integration tests."""

import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

os.environ["ORIGIN_ENV"] = "test"
os.environ["LAB_AUTO_SEED"] = "false"

from app.db.models import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
async def db_session(tmp_path: pytest.TempPathFactory) -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean async SQLite database session per test."""
    db_file = tmp_path / "test_origin.db"  # type: ignore[operator]
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_maker() as session:
        yield session

    await test_engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an HTTPX AsyncClient wired to the FastAPI app with test DB override."""

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()
