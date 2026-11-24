import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import DatabaseSettings
from app.log import setup_logging
from app.models import Base

config = context.config
target_metadata = Base.metadata

# Tests pass their own URL and keep their logging setup
database_url = config.attributes.get("database_url") or DatabaseSettings().database_url
if config.attributes.get("configure_logging", True):
    setup_logging("INFO")


def run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(run_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    context.configure(url=database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(run_async_migrations())
