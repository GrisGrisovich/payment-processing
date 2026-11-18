import asyncio

from alembic import context

from app.infrastructure.database import make_engine
from app.infrastructure.models import Base
from app.settings import DatabaseSettings


def migrate(connection):
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run():
    engine = make_engine(DatabaseSettings().database_url)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(migrate)
    finally:
        await engine.dispose()


asyncio.run(run())
