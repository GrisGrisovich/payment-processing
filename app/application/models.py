from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from app.application.types import PaymentStatus, WebhookState

type JsonValue = (
    str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
)
type Currency = Literal["RUB", "USD", "EUR"]


@dataclass(frozen=True, slots=True)
class PaymentData:
    amount: Decimal
    currency: Currency
    description: str
    metadata: JsonValue
    webhook_url: str


@dataclass(frozen=True, slots=True)
class Payment(PaymentData):
    payment_id: UUID
    status: PaymentStatus
    created_at: datetime
    processed_at: datetime | None
    webhook_state: WebhookState
    webhook_attempt: int


@dataclass(frozen=True, slots=True)
class PendingEvent:
    event_id: UUID
    payment_id: UUID
    destination: str
    attempt: int
