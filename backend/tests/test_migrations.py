from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from app.models import Base


async def test_migrations_match_models(db_engine):
    def find_differences(connection):
        context = MigrationContext.configure(connection)
        return compare_metadata(context, Base.metadata)

    async with db_engine.connect() as conn:
        differences = await conn.run_sync(find_differences)

    assert differences == []
