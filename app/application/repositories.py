from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.application.models import Payment, PaymentData, PendingEvent
from app.application.types import PaymentStatus, WebhookState


class PaymentRepository(Protocol):
    async def create_or_get(
        self, key: str, data: PaymentData
    ) -> tuple[Payment, bool]: ...

    async def get(self, payment_id: UUID) -> Payment | None: ...

    async def save_result(
        self, payment_id: UUID, status: PaymentStatus, processed_at: datetime
    ) -> None: ...

    async def save_delivery(
        self, payment_id: UUID, state: WebhookState, attempt: int
    ) -> None: ...


class OutboxRepository(Protocol):
    def enqueue(
        self, payment_id: UUID, destination: str, attempt: int, delay: int = 0
    ) -> None: ...

    async def next_ready(self) -> PendingEvent | None: ...

    async def mark_published(self, event_id: UUID) -> None: ...
