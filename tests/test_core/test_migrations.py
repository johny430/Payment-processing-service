from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from src.core.database.base import Base
from src.core.database.di import engine
from src.core.database.registry import import_all_models


def get_schema_diff(connection) -> list:
    context = MigrationContext.configure(connection, opts={'compare_type': True})
    return compare_metadata(context, Base.metadata)


async def test_migrations_match_models():
    import_all_models()

    async with engine.connect() as conn:
        diff = await conn.run_sync(get_schema_diff)

    assert diff == []
