import asyncio
import logging
from functools import partial

import httpx
from faststream import FastStream
from faststream.rabbit import Channel, RabbitBroker
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.application.services.processing import process_payment
from app.consumer.handler import register_payment_handler
from app.consumer.relay import OutboxRelay
from app.infrastructure.database import make_engine, postgres_unit_of_work
from app.infrastructure.gateway import simulate_gateway
from app.infrastructure.webhook import post_webhook
from app.settings import ConsumerSettings


async def main() -> None:
    settings = ConsumerSettings()
    broker = RabbitBroker(
        settings.rabbitmq_url,
        fail_fast=False,
        default_channel=Channel(
            prefetch_count=1, publisher_confirms=True, on_return_raises=True
        ),
    )
    engine = make_engine(settings.database_url)
    try:
        unit_of_work = partial(postgres_unit_of_work, async_sessionmaker(engine))
        relay = OutboxRelay(broker, unit_of_work)
        app = FastStream(
            broker,
            after_startup=(relay.start,),
            on_shutdown=(relay.stop,),
        )
        async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
            process = partial(
                process_payment,
                unit_of_work,
                run_gateway=simulate_gateway,
                send_webhook=partial(post_webhook, client),
                max_attempts=settings.webhook_max_attempts,
                base_retry_delay_seconds=settings.webhook_retry_base_delay_seconds,
            )
            register_payment_handler(broker, process)
            try:
                await app.run()
            finally:
                await relay.stop()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
