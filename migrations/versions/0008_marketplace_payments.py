"""marketplace order payments

Revision ID: 0008_marketplace_payments
Revises: 0007_provider_rating_numeric
Create Date: 2026-07-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0008_marketplace_payments"
down_revision = "0007_provider_rating_numeric"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column(
    "orders",
    sa.Column("financial_status", sa.String(length=40), nullable=False, server_default="awaiting_payment"),
  )
  op.create_index(op.f("ix_orders_financial_status"), "orders", ["financial_status"], unique=False)

  op.create_table(
    "stripe_connected_accounts",
    sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
    sa.Column("organization_id", postgresql.UUID(as_uuid=False), nullable=False),
    sa.Column("stripe_account_id", sa.String(length=120), nullable=False),
    sa.Column("onboarding_status", sa.String(length=40), nullable=False),
    sa.Column("charges_enabled", sa.Boolean(), server_default="false", nullable=False),
    sa.Column("payouts_enabled", sa.Boolean(), server_default="false", nullable=False),
    sa.Column("details_submitted", sa.Boolean(), server_default="false", nullable=False),
    sa.Column("default_currency", sa.String(length=10), server_default="brl", nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("organization_id"),
    sa.UniqueConstraint("stripe_account_id"),
  )
  op.create_index(
    op.f("ix_stripe_connected_accounts_organization_id"),
    "stripe_connected_accounts",
    ["organization_id"],
    unique=False,
  )
  op.create_index(
    op.f("ix_stripe_connected_accounts_stripe_account_id"),
    "stripe_connected_accounts",
    ["stripe_account_id"],
    unique=False,
  )

  op.create_table(
    "order_payments",
    sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
    sa.Column("organization_id", postgresql.UUID(as_uuid=False), nullable=False),
    sa.Column("order_id", postgresql.UUID(as_uuid=False), nullable=False),
    sa.Column("amount_cents", sa.Integer(), nullable=False),
    sa.Column("platform_fee_cents", sa.Integer(), nullable=False),
    sa.Column("net_amount_cents", sa.Integer(), nullable=False),
    sa.Column("currency", sa.String(length=10), server_default="brl", nullable=False),
    sa.Column("status", sa.String(length=40), nullable=False),
    sa.Column("stripe_checkout_session_id", sa.String(length=180), nullable=True),
    sa.Column("stripe_payment_intent_id", sa.String(length=180), nullable=True),
    sa.Column("stripe_transfer_destination", sa.String(length=120), nullable=False),
    sa.Column("receipt_number", sa.String(length=80), nullable=False),
    sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("payout_sent_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.CheckConstraint("amount_cents > 0", name="chk_order_payment_amount_positive"),
    sa.CheckConstraint("net_amount_cents >= 0", name="chk_order_payment_net_non_negative"),
    sa.CheckConstraint("platform_fee_cents >= 0", name="chk_order_payment_fee_non_negative"),
    sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
    sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id"),
    sa.UniqueConstraint("receipt_number"),
    sa.UniqueConstraint("stripe_checkout_session_id"),
  )
  op.create_index(op.f("ix_order_payments_order_id"), "order_payments", ["order_id"], unique=False)
  op.create_index(op.f("ix_order_payments_organization_id"), "order_payments", ["organization_id"], unique=False)
  op.create_index(op.f("ix_order_payments_status"), "order_payments", ["status"], unique=False)
  op.create_index(
    op.f("ix_order_payments_stripe_payment_intent_id"),
    "order_payments",
    ["stripe_payment_intent_id"],
    unique=False,
  )
  op.create_index("ix_order_payments_org_created", "order_payments", ["organization_id", "created_at"], unique=False)


def downgrade() -> None:
  op.drop_index("ix_order_payments_org_created", table_name="order_payments")
  op.drop_index(op.f("ix_order_payments_stripe_payment_intent_id"), table_name="order_payments")
  op.drop_index(op.f("ix_order_payments_status"), table_name="order_payments")
  op.drop_index(op.f("ix_order_payments_organization_id"), table_name="order_payments")
  op.drop_index(op.f("ix_order_payments_order_id"), table_name="order_payments")
  op.drop_table("order_payments")

  op.drop_index(op.f("ix_stripe_connected_accounts_stripe_account_id"), table_name="stripe_connected_accounts")
  op.drop_index(op.f("ix_stripe_connected_accounts_organization_id"), table_name="stripe_connected_accounts")
  op.drop_table("stripe_connected_accounts")

  op.drop_index(op.f("ix_orders_financial_status"), table_name="orders")
  op.drop_column("orders", "financial_status")
