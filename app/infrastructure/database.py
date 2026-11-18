from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.application.exceptions import PersistenceError
from app.infrastructure.repositories.outbox import PostgresOutboxRepository
from app.infrastructure.repositories.payments import PostgresPaymentRepository


def make_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, pool_pre_ping=True)


@dataclass(frozen=True, slots=True)
class PostgresUnitOfWork:
    payments: PostgresPaymentRepository
    outbox: PostgresOutboxRepository


@asynccontextmanager
async def postgres_unit_of_work(
    sessions: async_sessionmaker[AsyncSession],
) -> AsyncIterator[PostgresUnitOfWork]:
    try:
        async with sessions.begin() as session:
            yield PostgresUnitOfWork(
                payments=PostgresPaymentRepository(session),
                outbox=PostgresOutboxRepository(session),
            )
    except SQLAlchemyError as error:
        raise PersistenceError("PostgreSQL transaction failed") from error
