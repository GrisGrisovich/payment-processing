import asyncio
import random

from app.application.types import PaymentStatus


async def simulate_gateway() -> PaymentStatus:
    await asyncio.sleep(random.uniform(2, 5))
    return PaymentStatus.SUCCEEDED if random.random() < 0.9 else PaymentStatus.FAILED
