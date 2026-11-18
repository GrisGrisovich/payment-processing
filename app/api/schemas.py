from decimal import Decimal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, JsonValue

from app.application.models import Currency
from app.application.types import PaymentStatus


class CreatePayment(BaseModel):
    amount: Decimal = Field(gt=0, allow_inf_nan=False)
    currency: Currency
    description: str
    metadata: JsonValue
    webhook_url: HttpUrl


class PaymentCreated(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    payment_id: UUID
    status: PaymentStatus
    created_at: AwareDatetime


class PaymentDetail(PaymentCreated):
    amount: Decimal
    currency: Currency
    description: str
    metadata: JsonValue
    webhook_url: str
    processed_at: AwareDatetime | None
