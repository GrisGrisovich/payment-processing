import logging
from decimal import Decimal
from uuid import UUID

import httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict, JsonValue

from app.application.models import Currency, Payment
from app.application.types import PaymentStatus

logger = logging.getLogger(__name__)


class PaymentWebhook(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    payment_id: UUID
    amount: Decimal
    currency: Currency
    description: str
    metadata: JsonValue
    status: PaymentStatus
    created_at: AwareDatetime
    processed_at: AwareDatetime


async def post_webhook(client: httpx.AsyncClient, payment: Payment) -> bool:
    payload = PaymentWebhook.model_validate(payment)
    try:
        response = await client.post(
            payment.webhook_url, json=payload.model_dump(mode="json")
        )
    except httpx.RequestError as error:
        logger.warning(
            "Webhook for %s failed: %s", payment.payment_id, type(error).__name__
        )
        return False

    if not response.is_success:
        logger.warning(
            "Webhook for %s returned HTTP %s", payment.payment_id, response.status_code
        )
    return response.is_success
