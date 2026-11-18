import asyncio
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.types import PAYMENTS_QUEUE
from app.infrastructure.repositories.outbox import PostgresOutboxRepository

pytestmark = pytest.mark.asyncio
PAYMENTS = "/api/v1/payments"


async def test_creates_pending_payment_and_outbox(api, created_payment, stored_payment):
    response = await api.get(f"{PAYMENTS}/{created_payment['payment_id']}")

    assert response.status_code == 200
    detail = response.json()
    assert detail["status"] == created_payment["status"] == "pending"
    assert detail["processed_at"] is None
    assert Decimal(detail["amount"]) == Decimal("123.45")

    payment, events = await stored_payment()
    assert str(payment.id) == created_payment["payment_id"]
    assert [(event.destination, event.attempt) for event in events] == [
        (PAYMENTS_QUEUE, 1)
    ]


async def test_concurrent_equivalent_requests_create_one_payment(
    api, payment_body, stored_payment
):
    equivalent = payment_body | {
        "amount": "123.4500",
        "metadata": {"items": 2, "source": "test"},
    }

    first, second = await asyncio.gather(
        api.post(PAYMENTS, json=payment_body),
        api.post(PAYMENTS, json=equivalent),
    )

    assert first.status_code == second.status_code == 202
    assert first.json() == second.json()
    payment, events = await stored_payment()
    assert first.json()["payment_id"] == str(payment.id)
    assert len(events) == 1


async def test_changed_body_with_same_key_conflicts(api, payment_body, created_payment):
    response = await api.post(PAYMENTS, json=payment_body | {"amount": "123.46"})

    assert response.status_code == 409


@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.parametrize("key", [None, "wrong-key"], ids=["missing", "invalid"])
async def test_endpoints_require_the_api_key(api, payment_body, method, key):
    if key is None:
        del api.headers["X-API-Key"]
    else:
        api.headers["X-API-Key"] = key

    if method == "GET":
        response = await api.get(f"{PAYMENTS}/{uuid4()}")
    else:
        response = await api.post(PAYMENTS, json=payment_body)

    assert response.status_code == 401


async def test_unknown_payment_returns_404(api):
    response = await api.get(f"{PAYMENTS}/{uuid4()}")

    assert response.status_code == 404


@pytest.mark.parametrize(
    "changes",
    [{"currency": "GBP"}, {"amount": "0"}, {"webhook_url": "file:///tmp/a"}],
    ids=["currency", "amount", "webhook-url"],
)
async def test_invalid_payment_returns_422(api, payment_body, changes):
    response = await api.post(PAYMENTS, json=payment_body | changes)

    assert response.status_code == 422


async def test_missing_idempotency_key_returns_422(api, payment_body):
    del api.headers["Idempotency-Key"]
    response = await api.post(PAYMENTS, json=payment_body)

    assert response.status_code == 422


async def test_postgres_rejecting_outbox_rolls_back_payment(
    api, payment_body, stored_payment, monkeypatch
):
    enqueue = PostgresOutboxRepository.enqueue

    def enqueue_invalid_attempt(repository, payment_id, destination, attempt):
        enqueue(repository, payment_id, destination, attempt=0)

    with monkeypatch.context() as failure:
        failure.setattr(PostgresOutboxRepository, "enqueue", enqueue_invalid_attempt)
        response = await api.post(PAYMENTS, json=payment_body)

    assert response.status_code == 500
    assert await stored_payment() == (None, [])

    retry = await api.post(PAYMENTS, json=payment_body)
    assert retry.status_code == 202
    _, events = await stored_payment()
    assert len(events) == 1
