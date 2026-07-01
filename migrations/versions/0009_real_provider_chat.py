"""real provider chat links

Revision ID: 0009_real_provider_chat
Revises: 0008_marketplace_payments
Create Date: 2026-07-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0009_real_provider_chat"
down_revision = "0008_marketplace_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column("providers", sa.Column("organization_id", postgresql.UUID(as_uuid=False), nullable=True))
  op.add_column("providers", sa.Column("owner_user_id", postgresql.UUID(as_uuid=False), nullable=True))
  op.create_foreign_key(
    "fk_providers_organization_id_organizations",
    "providers",
    "organizations",
    ["organization_id"],
    ["id"],
    ondelete="CASCADE",
  )
  op.create_foreign_key(
    "fk_providers_owner_user_id_users",
    "providers",
    "users",
    ["owner_user_id"],
    ["id"],
    ondelete="SET NULL",
  )
  op.create_index(op.f("ix_providers_organization_id"), "providers", ["organization_id"], unique=True)
  op.create_index(op.f("ix_providers_owner_user_id"), "providers", ["owner_user_id"], unique=False)

  op.add_column("conversations", sa.Column("provider_id", postgresql.UUID(as_uuid=False), nullable=True))
  op.add_column("conversations", sa.Column("interest_request_id", postgresql.UUID(as_uuid=False), nullable=True))
  op.create_foreign_key(
    "fk_conversations_provider_id_providers",
    "conversations",
    "providers",
    ["provider_id"],
    ["id"],
    ondelete="SET NULL",
  )
  op.create_foreign_key(
    "fk_conversations_interest_request_id_interest_requests",
    "conversations",
    "interest_requests",
    ["interest_request_id"],
    ["id"],
    ondelete="SET NULL",
  )
  op.create_index(op.f("ix_conversations_provider_id"), "conversations", ["provider_id"], unique=False)
  op.create_index(op.f("ix_conversations_interest_request_id"), "conversations", ["interest_request_id"], unique=False)
  op.create_unique_constraint("uq_conversation_org_provider", "conversations", ["organization_id", "provider_id"])


def downgrade() -> None:
  op.drop_constraint("uq_conversation_org_provider", "conversations", type_="unique")
  op.drop_index(op.f("ix_conversations_interest_request_id"), table_name="conversations")
  op.drop_index(op.f("ix_conversations_provider_id"), table_name="conversations")
  op.drop_constraint("fk_conversations_interest_request_id_interest_requests", "conversations", type_="foreignkey")
  op.drop_constraint("fk_conversations_provider_id_providers", "conversations", type_="foreignkey")
  op.drop_column("conversations", "interest_request_id")
  op.drop_column("conversations", "provider_id")

  op.drop_index(op.f("ix_providers_owner_user_id"), table_name="providers")
  op.drop_index(op.f("ix_providers_organization_id"), table_name="providers")
  op.drop_constraint("fk_providers_owner_user_id_users", "providers", type_="foreignkey")
  op.drop_constraint("fk_providers_organization_id_organizations", "providers", type_="foreignkey")
  op.drop_column("providers", "owner_user_id")
  op.drop_column("providers", "organization_id")
