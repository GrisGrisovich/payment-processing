from enum import StrEnum


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class WebhookState(StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    EXHAUSTED = "exhausted"


PAYMENTS_QUEUE = "payments.new"
PAYMENTS_DLQ = "payments.dlq"
