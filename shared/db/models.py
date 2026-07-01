from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
  Boolean,
  CheckConstraint,
  Date,
  DateTime,
  ForeignKey,
  Index,
  Integer,
  Numeric,
  String,
  Text,
  UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


def _uuid() -> str:
  return str(uuid4())


class Organization(Base, TimestampMixin):
  __tablename__ = "organizations"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  name: Mapped[str] = mapped_column(String(200), nullable=False)
  phone: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
  description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class User(Base, TimestampMixin):
  __tablename__ = "users"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
  name: Mapped[str] = mapped_column(String(200), nullable=False)
  user_type: Mapped[str] = mapped_column(String(40), nullable=False, default="confeccao")
  business_profile: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
  main_services_csv: Mapped[str] = mapped_column(String(500), nullable=False, default="")
  password_hash: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

  is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class OrganizationMember(Base, TimestampMixin):
  __tablename__ = "organization_members"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  organization_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
  )
  user_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
  )
  role: Mapped[str] = mapped_column(String(40), nullable=False, default="owner")
  job_title: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
  member_status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
  permissions_csv: Mapped[str] = mapped_column(String(500), nullable=False, default="")
  last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

  __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_org_member"),)


class OAuthAccount(Base, TimestampMixin):
  __tablename__ = "oauth_accounts"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  user_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
  )
  provider: Mapped[str] = mapped_column(String(40), nullable=False)
  provider_account_id: Mapped[str] = mapped_column(String(200), nullable=False)

  access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
  refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
  expires_at: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

  __table_args__ = (
    UniqueConstraint("provider", "provider_account_id", name="uq_oauth_provider_account"),
    Index("ix_oauth_user_provider", "user_id", "provider"),
  )


class RefreshToken(Base, TimestampMixin):
  __tablename__ = "refresh_tokens"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
  organization_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
  )
  token_hash: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
  expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
  revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Plan(Base, TimestampMixin):
  __tablename__ = "plans"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  key: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)  # basic/professional/enterprise
  name: Mapped[str] = mapped_column(String(120), nullable=False)


class Subscription(Base, TimestampMixin):
  __tablename__ = "subscriptions"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  organization_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True
  )
  plan_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False)
  status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
  trial_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
  stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
  stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, unique=True)


class TechnicalSheet(Base, TimestampMixin):
  __tablename__ = "technical_sheets"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  organization_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
  )

  order_number: Mapped[str] = mapped_column(String(60), nullable=False)
  model_name: Mapped[str] = mapped_column(String(240), nullable=False)
  fabric: Mapped[str] = mapped_column(String(240), nullable=False)
  status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")

  size_grade_type: Mapped[str] = mapped_column(String(20), nullable=False, default="letter")
  sizes_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")  # JSON string for portability
  total_pieces: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
  observations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

  __table_args__ = (
    Index("ix_sheets_org_created", "organization_id", "created_at"),
    UniqueConstraint("organization_id", "order_number", "model_name", name="uq_sheet_order_model"),
  )


class TechnicalSheetStep(Base, TimestampMixin):
  __tablename__ = "technical_sheet_steps"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  organization_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
  )
  sheet_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("technical_sheets.id", ondelete="CASCADE"), nullable=False, index=True
  )
  step_id: Mapped[str] = mapped_column(String(40), nullable=False)  # modeling/cutting/...

  completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
  completed_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
  responsible: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

  __table_args__ = (
    UniqueConstraint("sheet_id", "step_id", name="uq_sheet_step"),
    Index("ix_sheet_steps_sheet", "sheet_id", "created_at"),
  )


class TechnicalSheetStepEnabled(Base, TimestampMixin):
  __tablename__ = "technical_sheet_step_enabled"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  organization_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
  )
  sheet_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("technical_sheets.id", ondelete="CASCADE"), nullable=False, index=True
  )
  step_id: Mapped[str] = mapped_column(String(40), nullable=False)
  enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

  __table_args__ = (UniqueConstraint("sheet_id", "step_id", name="uq_sheet_step_enabled"),)


class Provider(Base, TimestampMixin):
  __tablename__ = "providers"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  organization_id: Mapped[Optional[str]] = mapped_column(
    UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, unique=True, index=True
  )
  owner_user_id: Mapped[Optional[str]] = mapped_column(
    UUID(as_uuid=False), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
  )
  name: Mapped[str] = mapped_column(String(240), nullable=False)
  provider_type: Mapped[str] = mapped_column(String(60), nullable=False)  # Bordado/Lavanderia/...
  location: Mapped[Optional[str]] = mapped_column(String(240), nullable=True)
  capacity: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
  description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
  verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

  # Média fracionária das reviews (recalculada a cada avaliação); Numeric evita 4.4 virar 4.
  rating: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False, default=0)
  review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ProviderService(Base, TimestampMixin):
  __tablename__ = "provider_services"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  provider_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, index=True
  )
  label: Mapped[str] = mapped_column(String(120), nullable=False)

  __table_args__ = (UniqueConstraint("provider_id", "label", name="uq_provider_service"),)


class InterestRequest(Base, TimestampMixin):
  __tablename__ = "interest_requests"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  organization_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
  )
  provider_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("providers.id", ondelete="RESTRICT"), nullable=False, index=True
  )
  requester_user_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
  )

  message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
  target_city: Mapped[Optional[str]] = mapped_column(String(240), nullable=True)
  target_state: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
  status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")  # pending/matched/rejected

  __table_args__ = (Index("ix_interest_org_created", "organization_id", "created_at"),)


class Conversation(Base, TimestampMixin):
  __tablename__ = "conversations"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  organization_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
  )
  provider_id: Mapped[Optional[str]] = mapped_column(
    UUID(as_uuid=False), ForeignKey("providers.id", ondelete="SET NULL"), nullable=True, index=True
  )
  interest_request_id: Mapped[Optional[str]] = mapped_column(
    UUID(as_uuid=False), ForeignKey("interest_requests.id", ondelete="SET NULL"), nullable=True, index=True
  )
  order_id: Mapped[Optional[str]] = mapped_column(
    UUID(as_uuid=False), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True
  )
  title: Mapped[Optional[str]] = mapped_column(String(240), nullable=True)

  __table_args__ = (
    Index("ix_conversations_org_created", "organization_id", "created_at"),
    UniqueConstraint("organization_id", "provider_id", name="uq_conversation_org_provider"),
  )


class ConversationMember(Base, TimestampMixin):
  __tablename__ = "conversation_members"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  organization_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
  )
  conversation_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
  )
  user_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
  )
  role: Mapped[str] = mapped_column(String(40), nullable=False, default="member")
  last_read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

  __table_args__ = (UniqueConstraint("conversation_id", "user_id", name="uq_conversation_member"),)


class Message(Base, TimestampMixin):
  __tablename__ = "messages"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  organization_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
  )
  conversation_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
  )
  sender_user_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
  )
  body: Mapped[str] = mapped_column(Text, nullable=False)
  attachment_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
  attachment_name: Mapped[Optional[str]] = mapped_column(String(240), nullable=True)
  attachment_content_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

  __table_args__ = (Index("ix_messages_convo_created", "conversation_id", "created_at"),)


class Review(Base, TimestampMixin):
  __tablename__ = "reviews"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  organization_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
  )
  provider_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("providers.id", ondelete="RESTRICT"), nullable=False, index=True
  )
  author_user_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
  )

  rating: Mapped[int] = mapped_column(Integer, nullable=False)
  comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

  quality: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
  deadline: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
  communication: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

  __table_args__ = (
    CheckConstraint("rating >= 1 AND rating <= 5", name="chk_review_rating"),
    Index("ix_reviews_provider_created", "provider_id", "created_at"),
  )


class OrganizationInvite(Base, TimestampMixin):
  __tablename__ = "organization_invites"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  organization_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
  )
  email: Mapped[str] = mapped_column(String(320), nullable=False)
  job_title: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
  permissions_csv: Mapped[str] = mapped_column(String(500), nullable=False, default="")
  invited_by_user_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
  )
  status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
  token_hash: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
  expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
  accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

  __table_args__ = (
    Index("ix_org_invites_org_email", "organization_id", "email"),
    Index("ix_org_invites_status", "organization_id", "status"),
  )


class Order(Base, TimestampMixin):
  __tablename__ = "orders"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  organization_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
  )
  order_code: Mapped[str] = mapped_column(String(60), nullable=False)
  client_name: Mapped[str] = mapped_column(String(240), nullable=False)
  product_name: Mapped[str] = mapped_column(String(240), nullable=False)
  quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
  deadline: Mapped[date] = mapped_column(Date, nullable=False)
  priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
  notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
  stage: Mapped[str] = mapped_column(String(40), nullable=False, default="planejamento")
  progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
  unit_price: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
  financial_status: Mapped[str] = mapped_column(
    String(40), nullable=False, default="awaiting_payment", server_default="awaiting_payment", index=True
  )
  technical_sheet_id: Mapped[Optional[str]] = mapped_column(
    UUID(as_uuid=False), ForeignKey("technical_sheets.id", ondelete="SET NULL"), nullable=True, index=True
  )

  __table_args__ = (
    UniqueConstraint("organization_id", "order_code", name="uq_order_org_code"),
    CheckConstraint("progress >= 0 AND progress <= 100", name="chk_order_progress"),
    CheckConstraint("quantity >= 0", name="chk_order_quantity"),
    Index("ix_orders_org_stage", "organization_id", "stage"),
    Index("ix_orders_org_created", "organization_id", "created_at"),
    Index("ix_orders_org_deadline", "organization_id", "deadline"),
  )


class StripeConnectedAccount(Base, TimestampMixin):
  __tablename__ = "stripe_connected_accounts"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  organization_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
  )
  stripe_account_id: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
  onboarding_status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
  charges_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
  payouts_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
  details_submitted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
  default_currency: Mapped[str] = mapped_column(String(10), nullable=False, default="brl", server_default="brl")


class OrderPayment(Base, TimestampMixin):
  __tablename__ = "order_payments"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  organization_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
  )
  order_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
  )
  amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
  platform_fee_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
  net_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
  currency: Mapped[str] = mapped_column(String(10), nullable=False, default="brl", server_default="brl")
  status: Mapped[str] = mapped_column(String(40), nullable=False, default="checkout_created", index=True)
  stripe_checkout_session_id: Mapped[Optional[str]] = mapped_column(String(180), nullable=True, unique=True)
  stripe_payment_intent_id: Mapped[Optional[str]] = mapped_column(String(180), nullable=True, index=True)
  stripe_transfer_destination: Mapped[str] = mapped_column(String(120), nullable=False)
  stripe_refund_id: Mapped[Optional[str]] = mapped_column(String(180), nullable=True, index=True)
  refund_reason: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
  refunded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
  stripe_dispute_id: Mapped[Optional[str]] = mapped_column(String(180), nullable=True, index=True)
  dispute_status: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
  disputed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
  payment_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
  receipt_number: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
  paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
  payout_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

  __table_args__ = (
    CheckConstraint("amount_cents > 0", name="chk_order_payment_amount_positive"),
    CheckConstraint("platform_fee_cents >= 0", name="chk_order_payment_fee_non_negative"),
    CheckConstraint("net_amount_cents >= 0", name="chk_order_payment_net_non_negative"),
    Index("ix_order_payments_org_created", "organization_id", "created_at"),
  )


class OrderBatch(Base, TimestampMixin):
  __tablename__ = "order_batches"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  organization_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
  )
  order_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
  )
  lot_number: Mapped[str] = mapped_column(String(60), nullable=False)
  quantity_sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
  quantity_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
  status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
  sent_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
  completed_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

  __table_args__ = (
    UniqueConstraint("order_id", "lot_number", name="uq_order_batch_lot"),
    CheckConstraint("quantity_sent >= 0", name="chk_batch_quantity_sent"),
    CheckConstraint("quantity_completed >= 0", name="chk_batch_quantity_completed"),
    Index("ix_order_batches_order_created", "order_id", "created_at"),
  )


class InventoryItem(Base, TimestampMixin):
  __tablename__ = "inventory_items"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  organization_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
  )
  name: Mapped[str] = mapped_column(String(240), nullable=False)
  category: Mapped[str] = mapped_column(String(40), nullable=False)
  current_stock: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)
  min_stock: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)
  unit: Mapped[str] = mapped_column(String(40), nullable=False)
  unit_cost: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)
  supplier: Mapped[Optional[str]] = mapped_column(String(240), nullable=True)

  __table_args__ = (
    CheckConstraint("current_stock >= 0", name="chk_inventory_current_stock"),
    CheckConstraint("min_stock >= 0", name="chk_inventory_min_stock"),
    CheckConstraint("unit_cost >= 0", name="chk_inventory_unit_cost"),
    Index("ix_inventory_items_org_name", "organization_id", "name"),
    Index("ix_inventory_items_org_category", "organization_id", "category"),
  )


class InventoryMovement(Base, TimestampMixin):
  __tablename__ = "inventory_movements"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  organization_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
  )
  item_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False, index=True
  )
  movement_type: Mapped[str] = mapped_column(String(20), nullable=False)
  quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
  reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
  recorded_by_user_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
  )

  __table_args__ = (
    CheckConstraint("quantity > 0", name="chk_inventory_movement_quantity"),
    Index("ix_inventory_movements_item_created", "item_id", "created_at"),
    Index("ix_inventory_movements_org_created", "organization_id", "created_at"),
  )


class CostCalculation(Base, TimestampMixin):
  __tablename__ = "cost_calculations"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  organization_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
  )
  product_name: Mapped[str] = mapped_column(String(240), nullable=False)
  quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
  total_material_cost: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False, default=0)
  total_labor_cost: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False, default=0)
  total_cost: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False, default=0)
  cost_per_unit: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False, default=0)
  profit_margin: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
  suggested_price: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False, default=0)

  __table_args__ = (
    CheckConstraint("quantity > 0", name="chk_cost_calc_quantity"),
    CheckConstraint("profit_margin >= 0", name="chk_cost_calc_profit_margin"),
    Index("ix_cost_calculations_org_created", "organization_id", "created_at"),
  )


class CostCalculationMaterial(Base, TimestampMixin):
  __tablename__ = "cost_calculation_materials"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  organization_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
  )
  calculation_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("cost_calculations.id", ondelete="CASCADE"), nullable=False, index=True
  )
  name: Mapped[str] = mapped_column(String(240), nullable=False)
  quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)
  unit: Mapped[str] = mapped_column(String(40), nullable=False, default="")
  unit_cost: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)
  total_cost: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False, default=0)
  sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

  __table_args__ = (Index("ix_cost_materials_calc", "calculation_id", "sort_order"),)


class CostCalculationLabor(Base, TimestampMixin):
  __tablename__ = "cost_calculation_labor"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  organization_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
  )
  calculation_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("cost_calculations.id", ondelete="CASCADE"), nullable=False, index=True
  )
  description: Mapped[str] = mapped_column(String(240), nullable=False)
  hours: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False, default=0)
  hourly_rate: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)
  total_cost: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False, default=0)
  sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

  __table_args__ = (Index("ix_cost_labor_calc", "calculation_id", "sort_order"),)


class ProviderFavorite(Base, TimestampMixin):
  __tablename__ = "provider_favorites"

  id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=_uuid)
  organization_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
  )
  provider_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, index=True
  )
  user_id: Mapped[str] = mapped_column(
    UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
  )
  last_contact_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

  __table_args__ = (
    UniqueConstraint("organization_id", "user_id", "provider_id", name="uq_provider_favorite"),
    Index("ix_provider_favorites_org_user", "organization_id", "user_id"),
  )
