from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import bindparam, select, update
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.exceptions import IdempotencyConflict
from app.application.models import Currency, JsonValue, Payment, PaymentData
from app.application.types import PaymentStatus, WebhookState
from app.infrastructure.models import Payment as PaymentRow


def to_payment(row: PaymentRow) -> Payment:
    return Payment(
        payment_id=row.id,
        amount=row.amount,
        currency=cast(Currency, row.currency),
        description=row.description,
        metadata=cast(JsonValue, row.request_metadata),
        webhook_url=row.webhook_url,
        status=PaymentStatus(row.status),
        created_at=row.created_at,
        processed_at=row.processed_at,
        webhook_state=WebhookState(row.webhook_state),
        webhook_attempt=row.webhook_attempt,
    )


class PostgresPaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_or_get(self, key: str, data: PaymentData) -> tuple[Payment, bool]:
        statement = (
            insert(PaymentRow)
            .values(
                idempotency_key=key,
                amount=data.amount,
                currency=data.currency,
                description=data.description,
                request_metadata=data.metadata,
                webhook_url=data.webhook_url,
            )
            .on_conflict_do_nothing(index_elements=[PaymentRow.idempotency_key])
            .returning(PaymentRow)
        )
        row = await self.session.scalar(statement)
        if row is not None:
            return to_payment(row), True

        # Under READ COMMITTED, this SELECT can see the winning concurrent insert.
        row = await self.session.scalar(
            select(PaymentRow).where(
                PaymentRow.idempotency_key == key,
                PaymentRow.amount == data.amount,
                PaymentRow.currency == data.currency,
                PaymentRow.description == data.description,
                PaymentRow.request_metadata
                == bindparam("metadata", data.metadata, type_=JSONB),
                PaymentRow.webhook_url == data.webhook_url,
            )
        )
        if row is None:
            raise IdempotencyConflict
        return to_payment(row), False

    async def get(self, payment_id: UUID) -> Payment | None:
        row = await self.session.get(PaymentRow, payment_id)
        return to_payment(row) if row is not None else None

    async def save_result(
        self, payment_id: UUID, status: PaymentStatus, processed_at: datetime
    ) -> None:
        await self.session.execute(
            update(PaymentRow)
            .where(PaymentRow.id == payment_id)
            .values(status=status, processed_at=processed_at)
        )

    async def save_delivery(
        self, payment_id: UUID, state: WebhookState, attempt: int
    ) -> None:
        await self.session.execute(
            update(PaymentRow)
            .where(PaymentRow.id == payment_id)
            .values(webhook_state=state, webhook_attempt=attempt)
        )
