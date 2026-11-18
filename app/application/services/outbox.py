from collections.abc import Awaitable, Callable

from app.application.models import PendingEvent
from app.application.unit_of_work import UnitOfWorkFactory

type EventPublisher = Callable[[PendingEvent], Awaitable[None]]


async def publish_one(unit_of_work: UnitOfWorkFactory, publish: EventPublisher) -> bool:
    async with unit_of_work() as transaction:
        event = await transaction.outbox.next_ready()
        if event is None:
            return False

        await publish(event)
        await transaction.outbox.mark_published(event.event_id)
    return True
