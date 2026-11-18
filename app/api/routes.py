from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import (
    IdempotencyKey,
    PaymentServiceDependency,
    require_api_key,
)
from app.api.schemas import CreatePayment, PaymentCreated, PaymentDetail
from app.application.exceptions import IdempotencyConflict
from app.application.models import Payment, PaymentData

router = APIRouter(prefix="/api/v1/payments", dependencies=[Depends(require_api_key)])


@router.post("", status_code=202, response_model=PaymentCreated)
async def post_payment(
    payload: CreatePayment,
    service: PaymentServiceDependency,
    idempotency_key: IdempotencyKey,
) -> Payment:
    if not idempotency_key.strip():
        raise HTTPException(status_code=422, detail="Idempotency-Key must be nonempty")
    data = PaymentData(
        amount=payload.amount,
        currency=payload.currency,
        description=payload.description,
        metadata=payload.metadata,
        webhook_url=str(payload.webhook_url),
    )
    try:
        return await service.create(idempotency_key, data)
    except IdempotencyConflict as error:
        raise HTTPException(
            status_code=409, detail="Idempotency-Key already used"
        ) from error


@router.get("/{payment_id}", response_model=PaymentDetail)
async def read_payment(payment_id: UUID, service: PaymentServiceDependency) -> Payment:
    payment = await service.get(payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found")
    return payment
