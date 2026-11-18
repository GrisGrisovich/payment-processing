from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(
            "amount > 0 AND amount < 'Infinity'::numeric", name="ck_payment_amount"
        ),
        CheckConstraint(
            "currency IN ('RUB', 'USD', 'EUR')", name="ck_payment_currency"
        ),
        CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed')", name="ck_payment_status"
        ),
        CheckConstraint(
            "(processed_at IS NULL) = (status = 'pending')", name="ck_payment_processed"
        ),
        CheckConstraint("webhook_attempt >= 1", name="ck_payment_webhook_attempt"),
        CheckConstraint(
            "webhook_state IN ('pending', 'delivered', 'exhausted')",
            name="ck_payment_webhook_state",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    idempotency_key: Mapped[str] = mapped_column(Text, unique=True)
    amount: Mapped[Decimal] = mapped_column(Numeric)
    currency: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    request_metadata: Mapped[object] = mapped_column("metadata", JSONB)
    webhook_url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    webhook_attempt: Mapped[int] = mapped_column(SmallInteger, server_default=text("1"))
    webhook_state: Mapped[str] = mapped_column(Text, server_default="pending")


class OutboxEvent(Base):
    __tablename__ = "outbox"
    __table_args__ = (
        UniqueConstraint(
            "payment_id", "destination", "attempt", name="uq_outbox_delivery"
        ),
        CheckConstraint("attempt >= 1", name="ck_outbox_attempt"),
        Index(
            "ix_outbox_unpublished_available",
            "available_at",
            postgresql_where=text("published_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    payment_id: Mapped[UUID] = mapped_column(ForeignKey("payments.id"))
    destination: Mapped[str] = mapped_column(Text)
    attempt: Mapped[int] = mapped_column(SmallInteger)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
