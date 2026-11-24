import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from asgi_lifespan import LifespanManager
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.main import create_app
from tests.helpers import TEST_DATABASE_URL, make_settings

BACKEND_DIR = Path(__file__).resolve().parent.parent


async def _ensure_database(url: str) -> None:
    target = make_url(url)
    engine = create_async_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": target.database},
            )
            if not exists:
                await conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def database():
    """A fresh schema for the run: downgrading and upgrading also checks both directions."""
    asyncio.run(_ensure_database(TEST_DATABASE_URL))
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.attributes["database_url"] = TEST_DATABASE_URL
    config.attributes["configure_logging"] = False
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture(scope="session")
async def db_engine(database):
    engine = create_async_engine(TEST_DATABASE_URL)
    yield engine
    await engine.dispose()


@pytest.fixture
async def clean_db(db_engine):
    async with db_engine.begin() as conn:
        await conn.execute(text("TRUNCATE stream_offers, streams, campaigns, offers"))


@pytest.fixture
def make_client(clean_db):
    @asynccontextmanager
    async def factory(**settings_overrides):
        app = create_app(make_settings(**settings_overrides))
        transport = httpx.ASGITransport(app=app)
        async with (
            LifespanManager(app),
            httpx.AsyncClient(transport=transport, base_url="http://test") as client,
        ):
            yield client

    return factory


@pytest.fixture
async def client(make_client):
    async with make_client() as client:
        yield client
