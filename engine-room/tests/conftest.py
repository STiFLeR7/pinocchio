"""Shared test fixtures for Nexus test suite."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from nexus.api import create_app
from nexus.config import (
    DatabaseConfig,
    DiscordConfig,
    EmailConfig,
    ExecutionConfig,
    LoggingConfig,
    NexusSettings,
    OpenRouterConfig,
)
from nexus.database import Base

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path


@pytest.fixture
def test_settings(tmp_path: Path) -> NexusSettings:
    """Provide test settings with a temporary database."""
    db_path = tmp_path / "test_nexus.db"
    return NexusSettings(
        database=DatabaseConfig(url=f"sqlite+aiosqlite:///{db_path}"),
        discord=DiscordConfig(token="test-token", guild_id=123456, owner_ids=[111222333]),
        email=EmailConfig(
            smtp_host="localhost",
            smtp_port=587,
            username="test",
            password="test",
            from_address="test@test.com",
            to_address="test@test.com",
        ),
        openrouter=OpenRouterConfig(api_key="test-key"),
        execution=ExecutionConfig(),
        logging=LoggingConfig(level="DEBUG", format="console"),
    )


@pytest.fixture
async def db_engine(test_settings: NexusSettings) -> AsyncGenerator[AsyncEngine, None]:
    """Create test database engine with tables."""
    engine = create_async_engine(test_settings.database.url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session with rollback."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        # Seed default allowed repository registry for testing
        import os
        import sys
        import uuid

        from nexus.memory.models import RepositoryRegistryRecord

        session.add(
            RepositoryRegistryRecord(
                id=uuid.uuid4(),
                name="workspace_root",
                absolute_path=os.path.abspath("."),
                allowed_branches=["*"],
                allowed_commands=["*"],
                is_active=True,
            )
        )

        root_path = "C:\\" if sys.platform == "win32" else "/"
        session.add(
            RepositoryRegistryRecord(
                id=uuid.uuid4(),
                name="testing_root",
                absolute_path=root_path,
                allowed_branches=["*"],
                allowed_commands=["*"],
                is_active=True,
            )
        )
        await session.flush()

        yield session
        await session.rollback()


@pytest.fixture
async def client(
    test_settings: NexusSettings,
    db_engine: AsyncEngine,
) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP test client."""
    app = create_app(settings=test_settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
