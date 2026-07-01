from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ConnectedAccountOut(BaseModel):
  organization_id: str
  stripe_account_id: str | None = None
  onboarding_status: str = "not_started"
  charges_enabled: bool = False
  payouts_enabled: bool = False
  details_submitted: bool = False
  default_currency: str = "brl"


class AccountOnboardingLinkRequest(BaseModel):
  return_url: str | None = None
  refresh_url: str | None = None


class AccountOnboardingLinkResponse(BaseModel):
  onboarding_url: str


class OrderCheckoutSessionRequest(BaseModel):
  success_url: str
  cancel_url: str


class OrderCheckoutSessionResponse(BaseModel):
  checkout_url: str
  payment_id: str | None = None


class OrderPaymentOut(BaseModel):
  id: str
  organization_id: str
  order_id: str
  amount_cents: int
  platform_fee_cents: int
  net_amount_cents: int
  currency: str
  status: str
  receipt_number: str
  stripe_payment_intent_id: str | None = None
  stripe_refund_id: str | None = None
  refund_reason: str | None = None
  refunded_at: datetime | None = None
  stripe_dispute_id: str | None = None
  dispute_status: str | None = None
  disputed_at: datetime | None = None
  payment_error: str | None = None
  paid_at: datetime | None = None
  payout_sent_at: datetime | None = None


class OrderPaymentListItem(BaseModel):
  id: str
  order_id: str
  order_code: str
  client_name: str
  product_name: str
  amount_cents: int
  platform_fee_cents: int
  net_amount_cents: int
  currency: str
  status: str
  financial_status: str
  receipt_number: str
  paid_at: datetime | None = None
  payout_sent_at: datetime | None = None
  refunded_at: datetime | None = None
  dispute_status: str | None = None
  payment_error: str | None = None


class MarketplaceFinanceSummary(BaseModel):
  connected_account: ConnectedAccountOut
  total_paid_cents: int
  total_platform_fee_cents: int
  total_net_cents: int
  pending_payout_cents: int
  disputed_cents: int
  refundable_cents: int
  payments: list[OrderPaymentListItem]


class OrderRefundRequest(BaseModel):
  reason: str = "requested_by_customer"


class OrderReceiptOut(BaseModel):
  receipt_number: str
  order_id: str
  order_code: str
  client_name: str
  product_name: str
  quantity: int
  amount_cents: int
  platform_fee_cents: int
  net_amount_cents: int
  currency: str
  payment_status: str
  financial_status: str
  paid_at: datetime | None = None
  issued_at: datetime = Field(default_factory=datetime.utcnow)
