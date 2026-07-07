"""mercado pago marketplace

Revision ID: 0011_mercado_pago
Revises: 0010_finance_chat
Create Date: 2026-07-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0011_mercado_pago"
down_revision = "0010_finance_chat"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.create_table(
    "mercado_pago_connected_accounts",
    sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
    sa.Column("organization_id", postgresql.UUID(as_uuid=False), nullable=False),
    sa.Column("mp_user_id", sa.String(length=120), nullable=False),
    sa.Column("access_token", sa.Text(), nullable=False),
    sa.Column("refresh_token", sa.Text(), nullable=True),
    sa.Column("public_key", sa.String(length=180), nullable=True),
    sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("onboarding_status", sa.String(length=40), server_default="connected", nullable=False),
    sa.Column("live_mode", sa.Boolean(), server_default="false", nullable=False),
    sa.Column("default_currency", sa.String(length=10), server_default="brl", nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
    sa.PrimaryKeyConstraint("id"),
  )
  op.create_index(
    op.f("ix_mercado_pago_connected_accounts_organization_id"),
    "mercado_pago_connected_accounts",
    ["organization_id"],
    unique=True,
  )
  op.create_index(
    op.f("ix_mercado_pago_connected_accounts_mp_user_id"),
    "mercado_pago_connected_accounts",
    ["mp_user_id"],
    unique=True,
  )
  op.add_column("order_payments", sa.Column("mercado_pago_preference_id", sa.String(length=180), nullable=True))
  op.add_column("order_payments", sa.Column("mercado_pago_payment_id", sa.String(length=180), nullable=True))
  op.add_column("order_payments", sa.Column("mercado_pago_status_detail", sa.String(length=180), nullable=True))
  op.add_column("order_payments", sa.Column("mercado_pago_refund_id", sa.String(length=180), nullable=True))
  op.create_index(
    op.f("ix_order_payments_mercado_pago_payment_id"),
    "order_payments",
    ["mercado_pago_payment_id"],
    unique=False,
  )
  op.create_index(
    op.f("ix_order_payments_mercado_pago_refund_id"),
    "order_payments",
    ["mercado_pago_refund_id"],
    unique=False,
  )
  op.create_unique_constraint(
    "uq_order_payments_mercado_pago_preference_id",
    "order_payments",
    ["mercado_pago_preference_id"],
  )


def downgrade() -> None:
  op.drop_constraint("uq_order_payments_mercado_pago_preference_id", "order_payments", type_="unique")
  op.drop_index(op.f("ix_order_payments_mercado_pago_refund_id"), table_name="order_payments")
  op.drop_index(op.f("ix_order_payments_mercado_pago_payment_id"), table_name="order_payments")
  op.drop_column("order_payments", "mercado_pago_refund_id")
  op.drop_column("order_payments", "mercado_pago_status_detail")
  op.drop_column("order_payments", "mercado_pago_payment_id")
  op.drop_column("order_payments", "mercado_pago_preference_id")
  op.drop_index(op.f("ix_mercado_pago_connected_accounts_mp_user_id"), table_name="mercado_pago_connected_accounts")
  op.drop_index(op.f("ix_mercado_pago_connected_accounts_organization_id"), table_name="mercado_pago_connected_accounts")
  op.drop_table("mercado_pago_connected_accounts")
