import asyncio
import logging
from collections.abc import Awaitable, Callable
from uuid import UUID

from faststream import AckPolicy
from faststream.exceptions import NackMessage
from faststream.rabbit import RabbitBroker, RabbitQueue

from app.application.exceptions import PersistenceError
from app.application.types import PAYMENTS_QUEUE
from app.consumer.schemas import PaymentEvent

logger = logging.getLogger(__name__)


def register_payment_handler(
    broker: RabbitBroker, process: Callable[[UUID, int], Awaitable[None]]
) -> None:
    # A redelivery during reconnection must wait for the current handler to finish.
    processing_lock = asyncio.Lock()

    @broker.subscriber(
        RabbitQueue(PAYMENTS_QUEUE, durable=True),
        ack_policy=AckPolicy.REJECT_ON_ERROR,
    )
    async def handle_payment(event: PaymentEvent) -> None:
        async with processing_lock:
            try:
                await process(event.payment_id, event.attempt)
            except PersistenceError as error:
                logger.exception(
                    "Could not save payment %s. Will requeue.", event.payment_id
                )
                await asyncio.sleep(1)
                raise NackMessage(requeue=True) from error
