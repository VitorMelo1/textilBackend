"""product operations schema

Revision ID: 0003_product_operations_schema
Revises: 0002_add_password_hash
Create Date: 2026-05-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0003_product_operations_schema"
down_revision = "0002_add_password_hash"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column("organization_members", sa.Column("job_title", sa.String(length=120), nullable=True))
  op.add_column(
    "organization_members",
    sa.Column("member_status", sa.String(length=40), nullable=False, server_default=sa.text("'active'")),
  )
  op.add_column(
    "organization_members",
    sa.Column("permissions_csv", sa.String(length=500), nullable=False, server_default=sa.text("''")),
  )
  op.add_column("organization_members", sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True))

  op.add_column("interest_requests", sa.Column("target_city", sa.String(length=240), nullable=True))
  op.add_column("interest_requests", sa.Column("target_state", sa.String(length=2), nullable=True))

  op.create_table(
    "organization_invites",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column(
      "organization_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("organizations.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column("email", sa.String(length=320), nullable=False),
    sa.Column("job_title", sa.String(length=120), nullable=True),
    sa.Column("permissions_csv", sa.String(length=500), nullable=False, server_default=sa.text("''")),
    sa.Column(
      "invited_by_user_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("users.id", ondelete="RESTRICT"),
      nullable=False,
    ),
    sa.Column("status", sa.String(length=40), nullable=False, server_default=sa.text("'pending'")),
    sa.Column("token_hash", sa.String(length=200), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.UniqueConstraint("token_hash", name="uq_org_invite_token_hash"),
  )
  op.create_index("ix_org_invites_org", "organization_invites", ["organization_id"])
  op.create_index("ix_org_invites_invited_by", "organization_invites", ["invited_by_user_id"])
  op.create_index("ix_org_invites_org_email", "organization_invites", ["organization_id", "email"])
  op.create_index("ix_org_invites_status", "organization_invites", ["organization_id", "status"])

  op.create_table(
    "orders",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column(
      "organization_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("organizations.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column("order_code", sa.String(length=60), nullable=False),
    sa.Column("client_name", sa.String(length=240), nullable=False),
    sa.Column("product_name", sa.String(length=240), nullable=False),
    sa.Column("quantity", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("deadline", sa.Date(), nullable=False),
    sa.Column("priority", sa.String(length=20), nullable=False, server_default=sa.text("'medium'")),
    sa.Column("notes", sa.Text(), nullable=True),
    sa.Column("stage", sa.String(length=40), nullable=False, server_default=sa.text("'planejamento'")),
    sa.Column("progress", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column(
      "technical_sheet_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("technical_sheets.id", ondelete="SET NULL"),
      nullable=True,
    ),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.CheckConstraint("progress >= 0 AND progress <= 100", name="chk_order_progress"),
    sa.CheckConstraint("quantity >= 0", name="chk_order_quantity"),
    sa.UniqueConstraint("organization_id", "order_code", name="uq_order_org_code"),
  )
  op.create_index("ix_orders_org", "orders", ["organization_id"])
  op.create_index("ix_orders_org_stage", "orders", ["organization_id", "stage"])
  op.create_index("ix_orders_org_created", "orders", ["organization_id", "created_at"])
  op.create_index("ix_orders_org_deadline", "orders", ["organization_id", "deadline"])
  op.create_index("ix_orders_technical_sheet", "orders", ["technical_sheet_id"])

  op.create_table(
    "order_batches",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column(
      "organization_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("organizations.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column(
      "order_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("orders.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column("lot_number", sa.String(length=60), nullable=False),
    sa.Column("quantity_sent", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("quantity_completed", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("status", sa.String(length=40), nullable=False, server_default=sa.text("'pending'")),
    sa.Column("sent_date", sa.Date(), nullable=True),
    sa.Column("completed_date", sa.Date(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.CheckConstraint("quantity_sent >= 0", name="chk_batch_quantity_sent"),
    sa.CheckConstraint("quantity_completed >= 0", name="chk_batch_quantity_completed"),
    sa.UniqueConstraint("order_id", "lot_number", name="uq_order_batch_lot"),
  )
  op.create_index("ix_order_batches_org", "order_batches", ["organization_id"])
  op.create_index("ix_order_batches_order", "order_batches", ["order_id"])
  op.create_index("ix_order_batches_order_created", "order_batches", ["order_id", "created_at"])

  op.create_table(
    "inventory_items",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column(
      "organization_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("organizations.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column("name", sa.String(length=240), nullable=False),
    sa.Column("category", sa.String(length=40), nullable=False),
    sa.Column("current_stock", sa.Numeric(12, 3), nullable=False, server_default=sa.text("0")),
    sa.Column("min_stock", sa.Numeric(12, 3), nullable=False, server_default=sa.text("0")),
    sa.Column("unit", sa.String(length=40), nullable=False),
    sa.Column("unit_cost", sa.Numeric(12, 4), nullable=False, server_default=sa.text("0")),
    sa.Column("supplier", sa.String(length=240), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.CheckConstraint("current_stock >= 0", name="chk_inventory_current_stock"),
    sa.CheckConstraint("min_stock >= 0", name="chk_inventory_min_stock"),
    sa.CheckConstraint("unit_cost >= 0", name="chk_inventory_unit_cost"),
  )
  op.create_index("ix_inventory_items_org", "inventory_items", ["organization_id"])
  op.create_index("ix_inventory_items_org_name", "inventory_items", ["organization_id", "name"])
  op.create_index("ix_inventory_items_org_category", "inventory_items", ["organization_id", "category"])

  op.create_table(
    "inventory_movements",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column(
      "organization_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("organizations.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column(
      "item_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("inventory_items.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column("movement_type", sa.String(length=20), nullable=False),
    sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
    sa.Column("reason", sa.Text(), nullable=False, server_default=sa.text("''")),
    sa.Column(
      "recorded_by_user_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("users.id", ondelete="RESTRICT"),
      nullable=False,
    ),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.CheckConstraint("quantity > 0", name="chk_inventory_movement_quantity"),
  )
  op.create_index("ix_inventory_movements_org", "inventory_movements", ["organization_id"])
  op.create_index("ix_inventory_movements_item", "inventory_movements", ["item_id"])
  op.create_index("ix_inventory_movements_user", "inventory_movements", ["recorded_by_user_id"])
  op.create_index("ix_inventory_movements_item_created", "inventory_movements", ["item_id", "created_at"])
  op.create_index("ix_inventory_movements_org_created", "inventory_movements", ["organization_id", "created_at"])

  op.create_table(
    "cost_calculations",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column(
      "organization_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("organizations.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column("product_name", sa.String(length=240), nullable=False),
    sa.Column("quantity", sa.Integer(), nullable=False, server_default=sa.text("1")),
    sa.Column("total_material_cost", sa.Numeric(14, 4), nullable=False, server_default=sa.text("0")),
    sa.Column("total_labor_cost", sa.Numeric(14, 4), nullable=False, server_default=sa.text("0")),
    sa.Column("total_cost", sa.Numeric(14, 4), nullable=False, server_default=sa.text("0")),
    sa.Column("cost_per_unit", sa.Numeric(14, 4), nullable=False, server_default=sa.text("0")),
    sa.Column("profit_margin", sa.Numeric(5, 2), nullable=False, server_default=sa.text("0")),
    sa.Column("suggested_price", sa.Numeric(14, 4), nullable=False, server_default=sa.text("0")),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.CheckConstraint("quantity > 0", name="chk_cost_calc_quantity"),
    sa.CheckConstraint("profit_margin >= 0", name="chk_cost_calc_profit_margin"),
  )
  op.create_index("ix_cost_calculations_org", "cost_calculations", ["organization_id"])
  op.create_index("ix_cost_calculations_org_created", "cost_calculations", ["organization_id", "created_at"])

  op.create_table(
    "cost_calculation_materials",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column(
      "organization_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("organizations.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column(
      "calculation_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("cost_calculations.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column("name", sa.String(length=240), nullable=False),
    sa.Column("quantity", sa.Numeric(12, 3), nullable=False, server_default=sa.text("0")),
    sa.Column("unit", sa.String(length=40), nullable=False, server_default=sa.text("''")),
    sa.Column("unit_cost", sa.Numeric(12, 4), nullable=False, server_default=sa.text("0")),
    sa.Column("total_cost", sa.Numeric(14, 4), nullable=False, server_default=sa.text("0")),
    sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
  )
  op.create_index("ix_cost_materials_org", "cost_calculation_materials", ["organization_id"])
  op.create_index("ix_cost_materials_calc", "cost_calculation_materials", ["calculation_id", "sort_order"])

  op.create_table(
    "cost_calculation_labor",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column(
      "organization_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("organizations.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column(
      "calculation_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("cost_calculations.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column("description", sa.String(length=240), nullable=False),
    sa.Column("hours", sa.Numeric(8, 2), nullable=False, server_default=sa.text("0")),
    sa.Column("hourly_rate", sa.Numeric(12, 4), nullable=False, server_default=sa.text("0")),
    sa.Column("total_cost", sa.Numeric(14, 4), nullable=False, server_default=sa.text("0")),
    sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
  )
  op.create_index("ix_cost_labor_org", "cost_calculation_labor", ["organization_id"])
  op.create_index("ix_cost_labor_calc", "cost_calculation_labor", ["calculation_id", "sort_order"])

  op.create_table(
    "provider_favorites",
    sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
    sa.Column(
      "organization_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("organizations.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column(
      "provider_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("providers.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column(
      "user_id",
      postgresql.UUID(as_uuid=False),
      sa.ForeignKey("users.id", ondelete="CASCADE"),
      nullable=False,
    ),
    sa.Column("last_contact_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    sa.UniqueConstraint("organization_id", "user_id", "provider_id", name="uq_provider_favorite"),
  )
  op.create_index("ix_provider_favorites_org", "provider_favorites", ["organization_id"])
  op.create_index("ix_provider_favorites_provider", "provider_favorites", ["provider_id"])
  op.create_index("ix_provider_favorites_user", "provider_favorites", ["user_id"])
  op.create_index("ix_provider_favorites_org_user", "provider_favorites", ["organization_id", "user_id"])


def downgrade() -> None:
  op.drop_table("provider_favorites")
  op.drop_table("cost_calculation_labor")
  op.drop_table("cost_calculation_materials")
  op.drop_table("cost_calculations")
  op.drop_table("inventory_movements")
  op.drop_table("inventory_items")
  op.drop_table("order_batches")
  op.drop_table("orders")
  op.drop_table("organization_invites")

  op.drop_column("interest_requests", "target_state")
  op.drop_column("interest_requests", "target_city")

  op.drop_column("organization_members", "last_active_at")
  op.drop_column("organization_members", "permissions_csv")
  op.drop_column("organization_members", "member_status")
  op.drop_column("organization_members", "job_title")
