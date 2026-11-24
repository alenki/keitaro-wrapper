import asyncio
from contextlib import asynccontextmanager

import httpx
import pytest
from asgi_lifespan import LifespanManager
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.main import create_app
from tests.helpers import TEST_DATABASE_URL, make_settings


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


@pytest.fixture(scope="session", autouse=True)
def database():
    asyncio.run(_ensure_database(TEST_DATABASE_URL))


@pytest.fixture
def make_client():
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
