from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.application.models import Payment
from app.application.repositories import OutboxRepository, PaymentRepository
from app.application.services.processing import process_payment
from app.application.types import (
    PAYMENTS_DLQ,
    PAYMENTS_QUEUE,
    PaymentStatus,
    WebhookState,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
def payment():
    now = datetime.now(UTC)
    return Payment(
        payment_id=uuid4(),
        amount=Decimal("123.45"),
        currency="RUB",
        description="Order",
        metadata={"order": 42},
        webhook_url="http://receiver:9000/webhook",
        status=PaymentStatus.SUCCEEDED,
        created_at=now,
        processed_at=now,
        webhook_state=WebhookState.PENDING,
        webhook_attempt=1,
    )


@pytest.fixture
def transaction():
    return SimpleNamespace(
        payments=Mock(spec=PaymentRepository),
        outbox=Mock(spec=OutboxRepository),
    )


@pytest.fixture
def unit_of_work(transaction):
    @asynccontextmanager
    async def open_transaction():
        yield transaction

    return open_transaction


@pytest.mark.parametrize(
    ("attempt", "retry_destination", "retry_attempt", "delay", "state"),
    [
        pytest.param(
            1, PAYMENTS_QUEUE, 2, 1, WebhookState.PENDING, id="retry-after-1s"
        ),
        pytest.param(
            2, PAYMENTS_QUEUE, 3, 2, WebhookState.PENDING, id="retry-after-2s"
        ),
        pytest.param(3, PAYMENTS_DLQ, 3, 0, WebhookState.EXHAUSTED, id="dead-letter"),
    ],
)
async def test_failed_delivery_schedules_next_event(
    payment,
    transaction,
    unit_of_work,
    attempt,
    retry_destination,
    retry_attempt,
    delay,
    state,
):
    payment = replace(payment, webhook_attempt=attempt)
    transaction.payments.get.return_value = payment
    gateway = AsyncMock()
    sender = AsyncMock(return_value=False)

    await process_payment(
        unit_of_work,
        payment.payment_id,
        attempt,
        gateway,
        sender,
        max_attempts=3,
        base_retry_delay_seconds=1,
    )

    sender.assert_awaited_once_with(payment)
    gateway.assert_not_awaited()
    transaction.payments.save_delivery.assert_awaited_once_with(
        payment.payment_id, state, retry_attempt
    )
    event = transaction.outbox.enqueue.call_args
    assert event.args == (payment.payment_id, retry_destination, retry_attempt)
    assert event.kwargs.get("delay", 0) == delay


async def test_successful_delivery_does_not_schedule_another_event(
    payment, transaction, unit_of_work
):
    transaction.payments.get.return_value = payment
    gateway = AsyncMock()
    sender = AsyncMock(return_value=True)

    await process_payment(
        unit_of_work,
        payment.payment_id,
        1,
        gateway,
        sender,
        max_attempts=3,
        base_retry_delay_seconds=1,
    )

    sender.assert_awaited_once_with(payment)
    gateway.assert_not_awaited()
    transaction.payments.save_delivery.assert_awaited_once_with(
        payment.payment_id, WebhookState.DELIVERED, 1
    )
    transaction.outbox.enqueue.assert_not_called()


@pytest.mark.parametrize(
    ("state", "attempt"),
    [
        pytest.param(WebhookState.PENDING, 2, id="stale-attempt"),
        pytest.param(WebhookState.DELIVERED, 1, id="already-delivered"),
        pytest.param(WebhookState.EXHAUSTED, 1, id="already-exhausted"),
    ],
)
async def test_redelivery_does_not_repeat_completed_work(
    payment, transaction, unit_of_work, state, attempt
):
    transaction.payments.get.return_value = replace(
        payment, webhook_state=state, webhook_attempt=attempt
    )
    gateway = AsyncMock()
    sender = AsyncMock()

    await process_payment(
        unit_of_work,
        payment.payment_id,
        1,
        gateway,
        sender,
        max_attempts=3,
        base_retry_delay_seconds=1,
    )

    gateway.assert_not_awaited()
    sender.assert_not_awaited()
    transaction.payments.save_delivery.assert_not_awaited()
    transaction.outbox.enqueue.assert_not_called()
