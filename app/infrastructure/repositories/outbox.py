from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.models import PendingEvent
from app.infrastructure.models import OutboxEvent


class PostgresOutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def enqueue(
        self, payment_id: UUID, destination: str, attempt: int, delay: int = 0
    ) -> None:
        self.session.add(
            OutboxEvent(
                payment_id=payment_id,
                destination=destination,
                attempt=attempt,
                available_at=func.now() + timedelta(seconds=delay),
            )
        )

    async def next_ready(self) -> PendingEvent | None:
        row = await self.session.scalar(
            select(OutboxEvent)
            .where(
                OutboxEvent.published_at.is_(None),
                OutboxEvent.available_at <= func.now(),
            )
            .order_by(OutboxEvent.available_at, OutboxEvent.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if row is None:
            return None
        return PendingEvent(row.id, row.payment_id, row.destination, row.attempt)

    async def mark_published(self, event_id: UUID) -> None:
        await self.session.execute(
            update(OutboxEvent)
            .where(OutboxEvent.id == event_id)
            .values(published_at=func.now())
        )
