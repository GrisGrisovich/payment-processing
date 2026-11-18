from faststream.rabbit import RabbitBroker

from app.application.models import PendingEvent


async def publish_event(broker: RabbitBroker, event: PendingEvent) -> None:
    confirmation = await broker.publish(
        {"payment_id": str(event.payment_id), "attempt": event.attempt},
        queue=event.destination,
        message_id=str(event.event_id),
        mandatory=True,
        persist=True,
        timeout=5,
    )
    if confirmation is None:
        raise RuntimeError("RabbitMQ did not confirm publication")
