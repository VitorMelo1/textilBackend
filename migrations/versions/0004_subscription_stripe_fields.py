"""add stripe fields to subscriptions

Revision ID: 0004_subscription_stripe_fields
Revises: 0003_product_operations_schema
Create Date: 2026-05-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_subscription_stripe_fields"
down_revision = "0003_product_operations_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column("subscriptions", sa.Column("stripe_customer_id", sa.String(length=120), nullable=True))
  op.add_column("subscriptions", sa.Column("stripe_subscription_id", sa.String(length=120), nullable=True))
  op.create_index("ix_subscriptions_stripe_customer_id", "subscriptions", ["stripe_customer_id"])
  op.create_unique_constraint(
    "uq_subscriptions_stripe_subscription_id",
    "subscriptions",
    ["stripe_subscription_id"],
  )


def downgrade() -> None:
  op.drop_constraint("uq_subscriptions_stripe_subscription_id", "subscriptions", type_="unique")
  op.drop_index("ix_subscriptions_stripe_customer_id", table_name="subscriptions")
  op.drop_column("subscriptions", "stripe_subscription_id")
  op.drop_column("subscriptions", "stripe_customer_id")
