from uuid import UUID

from pydantic import BaseModel, Field


class PaymentEvent(BaseModel):
    payment_id: UUID
    attempt: int = Field(ge=1)
