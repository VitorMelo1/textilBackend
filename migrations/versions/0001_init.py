"""init

Revision ID: 0001_init
Revises:
Create Date: 2026-04-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.create_table(
    "organizations",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column("name", sa.String(length=200), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
  )

  op.create_table(
    "users",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column("email", sa.String(length=320), nullable=False),
    sa.Column("name", sa.String(length=200), nullable=False),
    sa.Column("user_type", sa.String(length=40), nullable=False, server_default=sa.text("'confeccao'")),
    sa.Column("business_profile", sa.String(length=40), nullable=True),
    sa.Column("main_services_csv", sa.String(length=500), nullable=False, server_default=sa.text("''")),
    sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.UniqueConstraint("email", name="uq_users_email"),
  )
  op.create_index("ix_users_email", "users", ["email"])

  op.create_table(
    "organization_members",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column(
      "organization_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("organizations.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    sa.Column("role", sa.String(length=40), nullable=False, server_default=sa.text("'owner'")),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
  )
  op.create_index("ix_org_members_org", "organization_members", ["organization_id"])
  op.create_index("ix_org_members_user", "organization_members", ["user_id"])

  op.create_table(
    "oauth_accounts",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    sa.Column("provider", sa.String(length=40), nullable=False),
    sa.Column("provider_account_id", sa.String(length=200), nullable=False),
    sa.Column("access_token", sa.Text(), nullable=True),
    sa.Column("refresh_token", sa.Text(), nullable=True),
    sa.Column("expires_at", sa.Integer(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.UniqueConstraint("provider", "provider_account_id", name="uq_oauth_provider_account"),
  )
  op.create_index("ix_oauth_user_provider", "oauth_accounts", ["user_id", "provider"])

  op.create_table(
    "refresh_tokens",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    sa.Column(
      "organization_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("organizations.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column("token_hash", sa.String(length=200), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.UniqueConstraint("token_hash", name="uq_refresh_token_hash"),
  )
  op.create_index("ix_refresh_tokens_org", "refresh_tokens", ["organization_id"])

  op.create_table(
    "plans",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column("key", sa.String(length=40), nullable=False),
    sa.Column("name", sa.String(length=120), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.UniqueConstraint("key", name="uq_plans_key"),
  )

  op.create_table(
    "subscriptions",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column(
      "organization_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("organizations.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column(
      "plan_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False
    ),
    sa.Column("status", sa.String(length=40), nullable=False, server_default=sa.text("'active'")),
    sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.UniqueConstraint("organization_id", name="uq_subscription_org"),
  )

  op.create_table(
    "technical_sheets",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column(
      "organization_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("organizations.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column("order_number", sa.String(length=60), nullable=False),
    sa.Column("model_name", sa.String(length=240), nullable=False),
    sa.Column("fabric", sa.String(length=240), nullable=False),
    sa.Column("status", sa.String(length=40), nullable=False, server_default=sa.text("'pending'")),
    sa.Column("size_grade_type", sa.String(length=20), nullable=False, server_default=sa.text("'letter'")),
    sa.Column("sizes_json", sa.Text(), nullable=False, server_default=sa.text("'{}'")),
    sa.Column("total_pieces", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("observations", sa.Text(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.UniqueConstraint("organization_id", "order_number", "model_name", name="uq_sheet_order_model"),
  )
  op.create_index("ix_sheets_org_created", "technical_sheets", ["organization_id", "created_at"])

  op.create_table(
    "technical_sheet_steps",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column(
      "organization_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("organizations.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column(
      "sheet_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("technical_sheets.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column("step_id", sa.String(length=40), nullable=False),
    sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    sa.Column("completed_date", sa.Date(), nullable=True),
    sa.Column("responsible", sa.String(length=200), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.UniqueConstraint("sheet_id", "step_id", name="uq_sheet_step"),
  )
  op.create_index("ix_sheet_steps_sheet", "technical_sheet_steps", ["sheet_id", "created_at"])

  op.create_table(
    "technical_sheet_step_enabled",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column(
      "organization_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("organizations.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column(
      "sheet_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("technical_sheets.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column("step_id", sa.String(length=40), nullable=False),
    sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.UniqueConstraint("sheet_id", "step_id", name="uq_sheet_step_enabled"),
  )

  op.create_table(
    "providers",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column("name", sa.String(length=240), nullable=False),
    sa.Column("provider_type", sa.String(length=60), nullable=False),
    sa.Column("location", sa.String(length=240), nullable=True),
    sa.Column("capacity", sa.String(length=120), nullable=True),
    sa.Column("description", sa.Text(), nullable=True),
    sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    sa.Column("rating", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("review_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
  )

  op.create_table(
    "provider_services",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column(
      "provider_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("providers.id", ondelete="CASCADE"), nullable=False
    ),
    sa.Column("label", sa.String(length=120), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.UniqueConstraint("provider_id", "label", name="uq_provider_service"),
  )
  op.create_index("ix_provider_services_provider", "provider_services", ["provider_id"])

  op.create_table(
    "interest_requests",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column(
      "organization_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("organizations.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column(
      "provider_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("providers.id", ondelete="RESTRICT"), nullable=False
    ),
    sa.Column(
      "requester_user_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("users.id", ondelete="RESTRICT"),
      nullable=False,
    ),
    sa.Column("message", sa.Text(), nullable=True),
    sa.Column("status", sa.String(length=40), nullable=False, server_default=sa.text("'pending'")),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
  )
  op.create_index("ix_interest_org_created", "interest_requests", ["organization_id", "created_at"])

  op.create_table(
    "conversations",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column(
      "organization_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("organizations.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column("title", sa.String(length=240), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
  )
  op.create_index("ix_conversations_org_created", "conversations", ["organization_id", "created_at"])

  op.create_table(
    "conversation_members",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column(
      "organization_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("organizations.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column(
      "conversation_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("conversations.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    sa.Column("role", sa.String(length=40), nullable=False, server_default=sa.text("'member'")),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.UniqueConstraint("conversation_id", "user_id", name="uq_conversation_member"),
  )
  op.create_index("ix_conversation_members_convo", "conversation_members", ["conversation_id"])
  op.create_index("ix_conversation_members_user", "conversation_members", ["user_id"])

  op.create_table(
    "messages",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column(
      "organization_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("organizations.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column(
      "conversation_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("conversations.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column(
      "sender_user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    ),
    sa.Column("body", sa.Text(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
  )
  op.create_index("ix_messages_convo_created", "messages", ["conversation_id", "created_at"])

  op.create_table(
    "reviews",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column(
      "organization_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("organizations.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column(
      "provider_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("providers.id", ondelete="RESTRICT"), nullable=False
    ),
    sa.Column(
      "author_user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    ),
    sa.Column("rating", sa.Integer(), nullable=False),
    sa.Column("comment", sa.Text(), nullable=True),
    sa.Column("quality", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("deadline", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("communication", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.CheckConstraint("rating >= 1 AND rating <= 5", name="chk_review_rating"),
  )
  op.create_index("ix_reviews_provider_created", "reviews", ["provider_id", "created_at"])


def downgrade() -> None:
  op.drop_index("ix_reviews_provider_created", table_name="reviews")
  op.drop_table("reviews")
  op.drop_index("ix_messages_convo_created", table_name="messages")
  op.drop_table("messages")
  op.drop_index("ix_conversation_members_user", table_name="conversation_members")
  op.drop_index("ix_conversation_members_convo", table_name="conversation_members")
  op.drop_table("conversation_members")
  op.drop_index("ix_conversations_org_created", table_name="conversations")
  op.drop_table("conversations")
  op.drop_index("ix_interest_org_created", table_name="interest_requests")
  op.drop_table("interest_requests")
  op.drop_index("ix_provider_services_provider", table_name="provider_services")
  op.drop_table("provider_services")
  op.drop_table("providers")
  op.drop_table("technical_sheet_step_enabled")
  op.drop_index("ix_sheet_steps_sheet", table_name="technical_sheet_steps")
  op.drop_table("technical_sheet_steps")
  op.drop_index("ix_sheets_org_created", table_name="technical_sheets")
  op.drop_table("technical_sheets")
  op.drop_table("subscriptions")
  op.drop_table("plans")
  op.drop_index("ix_refresh_tokens_org", table_name="refresh_tokens")
  op.drop_table("refresh_tokens")
  op.drop_index("ix_oauth_user_provider", table_name="oauth_accounts")
  op.drop_table("oauth_accounts")
  op.drop_index("ix_org_members_user", table_name="organization_members")
  op.drop_index("ix_org_members_org", table_name="organization_members")
  op.drop_table("organization_members")
  op.drop_index("ix_users_email", table_name="users")
  op.drop_table("users")
  op.drop_table("organizations")
