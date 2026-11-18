import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None


def upgrade():
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("idempotency_key", sa.Text(), nullable=False, unique=True),
        sa.Column("amount", sa.Numeric(), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("metadata", JSONB(), nullable=False),
        sa.Column("webhook_url", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "webhook_attempt",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("webhook_state", sa.Text(), nullable=False, server_default="pending"),
        sa.CheckConstraint(
            "amount > 0 AND amount < 'Infinity'::numeric", name="ck_payment_amount"
        ),
        sa.CheckConstraint(
            "currency IN ('RUB', 'USD', 'EUR')", name="ck_payment_currency"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed')", name="ck_payment_status"
        ),
        sa.CheckConstraint(
            "(processed_at IS NULL) = (status = 'pending')", name="ck_payment_processed"
        ),
        sa.CheckConstraint("webhook_attempt >= 1", name="ck_payment_webhook_attempt"),
        sa.CheckConstraint(
            "webhook_state IN ('pending', 'delivered', 'exhausted')",
            name="ck_payment_webhook_state",
        ),
    )
    op.create_table(
        "outbox",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "payment_id", sa.Uuid(), sa.ForeignKey("payments.id"), nullable=False
        ),
        sa.Column("destination", sa.Text(), nullable=False),
        sa.Column("attempt", sa.SmallInteger(), nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "payment_id", "destination", "attempt", name="uq_outbox_delivery"
        ),
        sa.CheckConstraint("attempt >= 1", name="ck_outbox_attempt"),
    )
    op.create_index(
        "ix_outbox_unpublished_available",
        "outbox",
        ["available_at"],
        postgresql_where=sa.text("published_at IS NULL"),
    )


def downgrade():
    op.drop_table("outbox")
    op.drop_table("payments")
