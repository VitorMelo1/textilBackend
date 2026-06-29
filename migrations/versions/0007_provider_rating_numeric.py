"""provider rating as numeric for fractional review averages

Revision ID: 0007_provider_rating_numeric
Revises: 0006_organization_profile_fields
Create Date: 2026-06-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0007_provider_rating_numeric"
down_revision = "0006_organization_profile_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.alter_column(
    "providers",
    "rating",
    existing_type=sa.Integer(),
    type_=sa.Numeric(3, 2),
    existing_nullable=False,
  )


def downgrade() -> None:
  op.alter_column(
    "providers",
    "rating",
    existing_type=sa.Numeric(3, 2),
    type_=sa.Integer(),
    existing_nullable=False,
    postgresql_using="round(rating)::integer",
  )
