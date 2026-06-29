"""add unit_price to orders

Revision ID: 0005_order_unit_price
Revises: 0004_subscription_stripe_fields
Create Date: 2026-06-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0005_order_unit_price"
down_revision = "0004_subscription_stripe_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column(
    "orders",
    sa.Column(
      "unit_price",
      sa.Numeric(precision=14, scale=4),
      nullable=False,
      server_default="0",
    ),
  )


def downgrade() -> None:
  op.drop_column("orders", "unit_price")
