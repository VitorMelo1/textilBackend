"""add phone and description to organizations

Revision ID: 0006_organization_profile_fields
Revises: 0005_order_unit_price
Create Date: 2026-06-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0006_organization_profile_fields"
down_revision = "0005_order_unit_price"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column("organizations", sa.Column("phone", sa.String(40), nullable=True))
  op.add_column("organizations", sa.Column("description", sa.Text, nullable=True))


def downgrade() -> None:
  op.drop_column("organizations", "phone")
  op.drop_column("organizations", "description")
