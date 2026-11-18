from uuid import UUID

from app.application.models import Payment, PaymentData
from app.application.types import PAYMENTS_QUEUE
from app.application.unit_of_work import UnitOfWorkFactory


class PaymentService:
    def __init__(self, unit_of_work: UnitOfWorkFactory) -> None:
        self.unit_of_work = unit_of_work

    async def create(self, key: str, data: PaymentData) -> Payment:
        async with self.unit_of_work() as transaction:
            payment, created = await transaction.payments.create_or_get(key, data)
            if created:
                transaction.outbox.enqueue(
                    payment.payment_id, PAYMENTS_QUEUE, attempt=1
                )
        return payment

    async def get(self, payment_id: UUID) -> Payment | None:
        async with self.unit_of_work() as transaction:
            return await transaction.payments.get(payment_id)
