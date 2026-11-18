import asyncio
import logging
from contextlib import suppress
from functools import partial

from faststream.rabbit import RabbitBroker, RabbitQueue

from app.application.services.outbox import EventPublisher, publish_one
from app.application.types import PAYMENTS_DLQ
from app.application.unit_of_work import UnitOfWorkFactory
from app.infrastructure.publisher import publish_event

logger = logging.getLogger(__name__)


class OutboxRelay:
    def __init__(self, broker: RabbitBroker, unit_of_work: UnitOfWorkFactory) -> None:
        self._broker = broker
        self._unit_of_work = unit_of_work
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        await self._broker.declare_queue(RabbitQueue(PAYMENTS_DLQ, durable=True))
        publish = partial(publish_event, self._broker)
        self._task = asyncio.create_task(publish_outbox(self._unit_of_work, publish))

    async def stop(self) -> None:
        task = self._task
        if task is not None:
            self._task = None
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


async def publish_outbox(
    unit_of_work: UnitOfWorkFactory, publish: EventPublisher
) -> None:
    while True:
        try:
            published = await publish_one(unit_of_work, publish)
        except Exception:
            logger.exception("Outbox publication failed. Will retry.")
            await asyncio.sleep(1)
        else:
            if not published:
                await asyncio.sleep(0.25)
