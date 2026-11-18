import os
from functools import partial
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.main import app, lifespan
from app.infrastructure.database import make_engine, postgres_unit_of_work
from app.infrastructure.models import OutboxEvent, Payment

API_KEY = "integration-test-key"


@pytest.fixture
def payment_body():
    return {
        "amount": "123.45",
        "currency": "RUB",
        "description": "Acceptance test",
        "metadata": {"source": "test", "items": 2},
        "webhook_url": "http://receiver:9000/webhook",
    }


@pytest.fixture
def configured_database_url(monkeypatch):
    database_url = os.getenv("PAYMENT_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip(
            "Set PAYMENT_TEST_DATABASE_URL to a migrated test PostgreSQL database"
        )
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("API_KEY", API_KEY)
    return database_url


@pytest_asyncio.fixture
async def sessions(configured_database_url):
    engine = make_engine(configured_database_url)
    try:
        yield async_sessionmaker(engine)
    finally:
        await engine.dispose()


@pytest.fixture
def unit_of_work(sessions):
    return partial(postgres_unit_of_work, sessions)


@pytest_asyncio.fixture
async def idempotency_key(sessions):
    key = uuid4().hex
    yield key
    async with sessions.begin() as session:
        await session.execute(
            delete(OutboxEvent).where(
                OutboxEvent.payment_id.in_(
                    select(Payment.id).where(Payment.idempotency_key == key)
                )
            )
        )
        await session.execute(delete(Payment).where(Payment.idempotency_key == key))


@pytest_asyncio.fixture
async def api(configured_database_url, idempotency_key):
    async with (
        lifespan(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
            headers={"X-API-Key": API_KEY, "Idempotency-Key": idempotency_key},
        ) as client,
    ):
        yield client


@pytest.fixture
def stored_payment(sessions, idempotency_key):
    async def load():
        async with sessions() as session:
            payment = await session.scalar(
                select(Payment).where(Payment.idempotency_key == idempotency_key)
            )
            if payment is None:
                return None, []
            events = await session.scalars(
                select(OutboxEvent)
                .where(OutboxEvent.payment_id == payment.id)
                .order_by(OutboxEvent.attempt, OutboxEvent.destination)
            )
            return payment, list(events)

    return load


@pytest_asyncio.fixture
async def created_payment(api, payment_body):
    response = await api.post("/api/v1/payments", json=payment_body)
    assert response.status_code == 202, response.text
    return response.json()
