"""production finance and chat controls

Revision ID: 0010_production_finance_chat_controls
Revises: 0009_real_provider_chat
Create Date: 2026-07-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0010_production_finance_chat_controls"
down_revision = "0009_real_provider_chat"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column("order_payments", sa.Column("stripe_refund_id", sa.String(length=180), nullable=True))
  op.add_column("order_payments", sa.Column("refund_reason", sa.String(length=120), nullable=True))
  op.add_column("order_payments", sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True))
  op.add_column("order_payments", sa.Column("stripe_dispute_id", sa.String(length=180), nullable=True))
  op.add_column("order_payments", sa.Column("dispute_status", sa.String(length=80), nullable=True))
  op.add_column("order_payments", sa.Column("disputed_at", sa.DateTime(timezone=True), nullable=True))
  op.add_column("order_payments", sa.Column("payment_error", sa.Text(), nullable=True))
  op.create_index(op.f("ix_order_payments_stripe_refund_id"), "order_payments", ["stripe_refund_id"], unique=False)
  op.create_index(op.f("ix_order_payments_stripe_dispute_id"), "order_payments", ["stripe_dispute_id"], unique=False)

  op.add_column("conversations", sa.Column("order_id", postgresql.UUID(as_uuid=False), nullable=True))
  op.create_foreign_key(
    "fk_conversations_order_id_orders",
    "conversations",
    "orders",
    ["order_id"],
    ["id"],
    ondelete="SET NULL",
  )
  op.create_index(op.f("ix_conversations_order_id"), "conversations", ["order_id"], unique=False)

  op.add_column("conversation_members", sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True))

  op.add_column("messages", sa.Column("attachment_url", sa.Text(), nullable=True))
  op.add_column("messages", sa.Column("attachment_name", sa.String(length=240), nullable=True))
  op.add_column("messages", sa.Column("attachment_content_type", sa.String(length=120), nullable=True))


def downgrade() -> None:
  op.drop_column("messages", "attachment_content_type")
  op.drop_column("messages", "attachment_name")
  op.drop_column("messages", "attachment_url")

  op.drop_column("conversation_members", "last_read_at")

  op.drop_index(op.f("ix_conversations_order_id"), table_name="conversations")
  op.drop_constraint("fk_conversations_order_id_orders", "conversations", type_="foreignkey")
  op.drop_column("conversations", "order_id")

  op.drop_index(op.f("ix_order_payments_stripe_dispute_id"), table_name="order_payments")
  op.drop_index(op.f("ix_order_payments_stripe_refund_id"), table_name="order_payments")
  op.drop_column("order_payments", "payment_error")
  op.drop_column("order_payments", "disputed_at")
  op.drop_column("order_payments", "dispute_status")
  op.drop_column("order_payments", "stripe_dispute_id")
  op.drop_column("order_payments", "refunded_at")
  op.drop_column("order_payments", "refund_reason")
  op.drop_column("order_payments", "stripe_refund_id")
