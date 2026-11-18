import asyncio
import json
from datetime import timedelta
from functools import partial
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
from sqlalchemy import func, select

from app.application.services.outbox import publish_one
from app.application.services.processing import process_payment
from app.application.types import PAYMENTS_QUEUE, PaymentStatus, WebhookState
from app.infrastructure.webhook import post_webhook

pytestmark = pytest.mark.asyncio


async def test_outbox_stays_pending_until_publisher_succeeds(
    created_payment, stored_payment, unit_of_work
):
    _, events = await stored_payment()
    publish = AsyncMock(side_effect=[ConnectionError("broker unavailable"), None])

    with pytest.raises(ConnectionError, match="broker unavailable"):
        await publish_one(unit_of_work, publish)

    _, pending = await stored_payment()
    assert pending[0].published_at is None

    assert await publish_one(unit_of_work, publish)
    _, published = await stored_payment()
    assert published[0].published_at is not None
    attempted_events = [call.args[0] for call in publish.await_args_list]
    assert [event.event_id for event in attempted_events] == [events[0].id] * 2
    assert all(
        str(event.payment_id) == created_payment["payment_id"]
        for event in attempted_events
    )


@pytest.mark.parametrize("outcome", [PaymentStatus.SUCCEEDED, PaymentStatus.FAILED])
async def test_webhook_matches_saved_payment(
    api, created_payment, payment_body, unit_of_work, outcome
):
    payment_id = UUID(created_payment["payment_id"])
    received = []

    def receive(request: httpx.Request) -> httpx.Response:
        received.append(request)
        return httpx.Response(200)

    async with httpx.AsyncClient(transport=httpx.MockTransport(receive)) as client:
        await process_payment(
            unit_of_work,
            payment_id,
            1,
            AsyncMock(return_value=outcome),
            partial(post_webhook, client),
            max_attempts=3,
            base_retry_delay_seconds=1,
        )

    read = await api.get(f"/api/v1/payments/{payment_id}")
    assert read.status_code == 200
    details = read.json()
    assert details["status"] == outcome
    assert details["processed_at"] is not None
    expected_url = details.pop("webhook_url")
    assert len(received) == 1
    assert received[0].method == "POST"
    assert str(received[0].url) == expected_url == payment_body["webhook_url"]
    assert json.loads(received[0].content) == details


async def test_retry_attempt_and_available_at_are_saved_together(
    created_payment, sessions, stored_payment, unit_of_work
):
    payment_id = UUID(created_payment["payment_id"])
    async with sessions() as session:
        before = await session.scalar(select(func.now()))

    await process_payment(
        unit_of_work,
        payment_id,
        1,
        AsyncMock(return_value=PaymentStatus.SUCCEEDED),
        AsyncMock(return_value=False),
        max_attempts=3,
        base_retry_delay_seconds=1,
    )

    payment, events = await stored_payment()
    assert payment.webhook_attempt == 2
    assert payment.webhook_state == WebhookState.PENDING
    assert [(event.destination, event.attempt) for event in events] == [
        (PAYMENTS_QUEUE, 1),
        (PAYMENTS_QUEUE, 2),
    ]
    assert events[1].available_at >= before + timedelta(seconds=1)


async def test_redelivery_reuses_committed_gateway_result(
    created_payment, stored_payment, unit_of_work
):
    payment_id = UUID(created_payment["payment_id"])
    gateway = AsyncMock(return_value=PaymentStatus.SUCCEEDED)
    interrupted = AsyncMock(side_effect=asyncio.CancelledError)

    with pytest.raises(asyncio.CancelledError):
        await process_payment(
            unit_of_work,
            payment_id,
            1,
            gateway,
            interrupted,
            max_attempts=3,
            base_retry_delay_seconds=1,
        )

    saved, _ = await stored_payment()
    assert saved.status == PaymentStatus.SUCCEEDED
    assert saved.processed_at is not None
    assert saved.webhook_state == WebhookState.PENDING

    sender = AsyncMock(return_value=True)
    await process_payment(
        unit_of_work,
        payment_id,
        1,
        gateway,
        sender,
        max_attempts=3,
        base_retry_delay_seconds=1,
    )

    gateway.assert_awaited_once()
    sender.assert_awaited_once()
    assert sender.await_args.args[0].processed_at == saved.processed_at
    delivered, _ = await stored_payment()
    assert delivered.webhook_state == WebhookState.DELIVERED
