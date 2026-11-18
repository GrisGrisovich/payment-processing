from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from app.application.models import Payment
from app.application.types import (
    PAYMENTS_DLQ,
    PAYMENTS_QUEUE,
    PaymentStatus,
    WebhookState,
)
from app.application.unit_of_work import UnitOfWorkFactory

type PaymentGateway = Callable[[], Awaitable[PaymentStatus]]
type WebhookSender = Callable[[Payment], Awaitable[bool]]


async def process_payment(
    unit_of_work: UnitOfWorkFactory,
    payment_id: UUID,
    attempt: int,
    run_gateway: PaymentGateway,
    send_webhook: WebhookSender,
    *,
    max_attempts: int,
    base_retry_delay_seconds: int,
) -> None:
    async with unit_of_work() as transaction:
        payment = await transaction.payments.get(payment_id)

    if (
        payment is None
        or payment.webhook_state != WebhookState.PENDING
        or payment.webhook_attempt != attempt
    ):
        return

    if payment.status == PaymentStatus.PENDING:
        outcome = await run_gateway()
        processed_at = datetime.now(UTC)
        async with unit_of_work() as transaction:
            await transaction.payments.save_result(payment_id, outcome, processed_at)
        payment = replace(payment, status=outcome, processed_at=processed_at)

    delivered = await send_webhook(payment)

    async with unit_of_work() as transaction:
        if delivered:
            await transaction.payments.save_delivery(
                payment_id, WebhookState.DELIVERED, attempt
            )
        elif attempt >= max_attempts:
            await transaction.payments.save_delivery(
                payment_id, WebhookState.EXHAUSTED, attempt
            )
            transaction.outbox.enqueue(payment_id, PAYMENTS_DLQ, attempt)
        else:
            next_attempt = attempt + 1
            await transaction.payments.save_delivery(
                payment_id, WebhookState.PENDING, next_attempt
            )
            transaction.outbox.enqueue(
                payment_id,
                PAYMENTS_QUEUE,
                next_attempt,
                delay=base_retry_delay_seconds * 2 ** (attempt - 1),
            )
