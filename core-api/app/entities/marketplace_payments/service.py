from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import get_settings
from shared.db.models import Order, OrderPayment, StripeConnectedAccount

from . import repo
from .schemas import (
  ConnectedAccountOut,
  MarketplaceFinanceSummary,
  OrderCheckoutSessionResponse,
  OrderPaymentListItem,
  OrderPaymentOut,
  OrderReceiptOut,
)

try:
  import stripe
except Exception:  # pragma: no cover
  stripe = None  # type: ignore[assignment]


PAYMENT_STATUS_AWAITING = "awaiting_payment"
PAYMENT_STATUS_CHECKOUT_CREATED = "checkout_created"
PAYMENT_STATUS_PAID = "paid"
PAYMENT_STATUS_PAYOUT_SENT = "payout_sent"
PAYMENT_STATUS_REFUND_PENDING = "refund_pending"
PAYMENT_STATUS_REFUNDED = "refunded"
PAYMENT_STATUS_DISPUTED = "disputed"
PAYMENT_STATUS_FAILED = "payment_failed"
PAYMENT_STATUS_CANCELLED = "cancelled"


def _require_stripe():
  settings = get_settings()
  if stripe is None:
    raise HTTPException(status_code=500, detail="stripe package not installed")
  if not settings.STRIPE_SECRET_KEY:
    raise HTTPException(status_code=503, detail="stripe not configured")
  stripe.api_key = settings.STRIPE_SECRET_KEY
  return settings


def _stripe_obj_get(obj, key: str, default=None):
  if isinstance(obj, dict):
    return obj.get(key, default)
  return getattr(obj, key, default)


def calculate_platform_fee_cents(amount_cents: int) -> int:
  settings = get_settings()
  percent_fee = int(
    (Decimal(amount_cents) * Decimal(str(settings.PLATFORM_FEE_PERCENT)) / Decimal("100"))
    .quantize(Decimal("1"), rounding=ROUND_HALF_UP)
  )
  return max(percent_fee, int(settings.PLATFORM_FEE_MIN_CENTS))


def _order_amount_cents(order: Order) -> int:
  amount = Decimal(str(order.unit_price or 0)) * Decimal(int(order.quantity or 0))
  return int((amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _connected_account_out(organization_id: str, account: StripeConnectedAccount | None) -> ConnectedAccountOut:
  if account is None:
    return ConnectedAccountOut(organization_id=organization_id)
  return ConnectedAccountOut(
    organization_id=account.organization_id,
    stripe_account_id=account.stripe_account_id,
    onboarding_status=account.onboarding_status,
    charges_enabled=account.charges_enabled,
    payouts_enabled=account.payouts_enabled,
    details_submitted=account.details_submitted,
    default_currency=account.default_currency,
  )


def _payment_out(payment: OrderPayment) -> OrderPaymentOut:
  return OrderPaymentOut(
    id=payment.id,
    organization_id=payment.organization_id,
    order_id=payment.order_id,
    amount_cents=payment.amount_cents,
    platform_fee_cents=payment.platform_fee_cents,
    net_amount_cents=payment.net_amount_cents,
    currency=payment.currency,
    status=payment.status,
    receipt_number=payment.receipt_number,
    stripe_payment_intent_id=payment.stripe_payment_intent_id,
    stripe_refund_id=payment.stripe_refund_id,
    refund_reason=payment.refund_reason,
    refunded_at=payment.refunded_at,
    stripe_dispute_id=payment.stripe_dispute_id,
    dispute_status=payment.dispute_status,
    disputed_at=payment.disputed_at,
    payment_error=payment.payment_error,
    paid_at=payment.paid_at,
    payout_sent_at=payment.payout_sent_at,
  )


def _account_ready(account: StripeConnectedAccount) -> bool:
  return bool(account.charges_enabled and account.payouts_enabled and account.details_submitted)


def _payment_list_item(payment: OrderPayment, order: Order) -> OrderPaymentListItem:
  return OrderPaymentListItem(
    id=payment.id,
    order_id=order.id,
    order_code=order.order_code,
    client_name=order.client_name,
    product_name=order.product_name,
    amount_cents=payment.amount_cents,
    platform_fee_cents=payment.platform_fee_cents,
    net_amount_cents=payment.net_amount_cents,
    currency=payment.currency,
    status=payment.status,
    financial_status=order.financial_status,
    receipt_number=payment.receipt_number,
    paid_at=payment.paid_at,
    payout_sent_at=payment.payout_sent_at,
    refunded_at=payment.refunded_at,
    dispute_status=payment.dispute_status,
    payment_error=payment.payment_error,
  )


async def get_connected_account_status(
  session: AsyncSession,
  *,
  organization_id: str,
) -> ConnectedAccountOut:
  account = await repo.get_connected_account(session, organization_id=organization_id)
  return _connected_account_out(organization_id, account)


async def ensure_connected_account(
  session: AsyncSession,
  *,
  organization_id: str,
) -> ConnectedAccountOut:
  existing = await repo.get_connected_account(session, organization_id=organization_id)
  if existing is not None:
    return _connected_account_out(organization_id, existing)

  settings = _require_stripe()
  account = stripe.Account.create(
    type="express",
    country="BR",
    capabilities={
      "card_payments": {"requested": True},
      "transfers": {"requested": True},
    },
    business_type="company",
    metadata={"organization_id": organization_id},
  )
  row = StripeConnectedAccount(
    organization_id=organization_id,
    stripe_account_id=str(_stripe_obj_get(account, "id")),
    onboarding_status="pending",
    default_currency=settings.MARKETPLACE_CURRENCY.lower(),
  )
  await repo.create_connected_account(session, row)
  return _connected_account_out(organization_id, row)


async def create_onboarding_link(
  session: AsyncSession,
  *,
  organization_id: str,
  return_url: str | None,
  refresh_url: str | None,
) -> str:
  account_out = await ensure_connected_account(session, organization_id=organization_id)
  settings = _require_stripe()
  resolved_return = return_url or settings.STRIPE_CONNECT_RETURN_URL
  resolved_refresh = refresh_url or settings.STRIPE_CONNECT_REFRESH_URL
  if not resolved_return or not resolved_refresh:
    raise HTTPException(status_code=400, detail="return_url and refresh_url are required")

  link = stripe.AccountLink.create(
    account=account_out.stripe_account_id,
    refresh_url=resolved_refresh,
    return_url=resolved_return,
    type="account_onboarding",
  )
  return str(_stripe_obj_get(link, "url"))


async def sync_connected_account_snapshot(
  session: AsyncSession,
  *,
  stripe_account_id: str,
) -> ConnectedAccountOut | None:
  account = await repo.get_connected_account_by_stripe_id(session, stripe_account_id=stripe_account_id)
  if account is None:
    return None
  _require_stripe()
  stripe_account = stripe.Account.retrieve(stripe_account_id)
  account.charges_enabled = bool(_stripe_obj_get(stripe_account, "charges_enabled", False))
  account.payouts_enabled = bool(_stripe_obj_get(stripe_account, "payouts_enabled", False))
  account.details_submitted = bool(_stripe_obj_get(stripe_account, "details_submitted", False))
  account.onboarding_status = "ready" if account.charges_enabled and account.payouts_enabled else "pending"
  account.default_currency = str(_stripe_obj_get(stripe_account, "default_currency", account.default_currency))
  await session.flush()
  return _connected_account_out(account.organization_id, account)


async def sync_connected_account_for_org(
  session: AsyncSession,
  *,
  organization_id: str,
) -> ConnectedAccountOut:
  account = await repo.get_connected_account(session, organization_id=organization_id)
  if account is None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="connected account not configured")
  synced = await sync_connected_account_snapshot(session, stripe_account_id=account.stripe_account_id)
  return synced or _connected_account_out(organization_id, account)


async def create_order_checkout_session(
  session: AsyncSession,
  *,
  organization_id: str,
  order_id: str,
  success_url: str,
  cancel_url: str,
) -> OrderCheckoutSessionResponse:
  order = await repo.get_order(session, order_id=order_id)
  if order is None or order.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="order not found")
  if order.financial_status == PAYMENT_STATUS_PAID:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="order already paid")

  account = await repo.get_connected_account(session, organization_id=organization_id)
  if account is None:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="connected account not configured")
  if not _account_ready(account):
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="connected account is not ready to receive payments")

  amount_cents = _order_amount_cents(order)
  if amount_cents <= 0:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="order amount must be greater than zero")

  current = await repo.get_current_payment(session, order_id=order_id)
  if current is not None and current.status == PAYMENT_STATUS_PAID:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="order already paid")

  settings = _require_stripe()
  fee_cents = calculate_platform_fee_cents(amount_cents)
  net_cents = max(amount_cents - fee_cents, 0)
  receipt_number = f"REC-{order.order_code}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

  checkout = stripe.checkout.Session.create(
    mode="payment",
    payment_method_types=["card"],
    line_items=[
      {
        "price_data": {
          "currency": settings.MARKETPLACE_CURRENCY.lower(),
          "product_data": {"name": f"{order.order_code} - {order.product_name}"},
          "unit_amount": amount_cents,
        },
        "quantity": 1,
      }
    ],
    success_url=success_url,
    cancel_url=cancel_url,
    client_reference_id=order_id,
    metadata={
      "payment_scope": "order",
      "organization_id": organization_id,
      "order_id": order_id,
      "receipt_number": receipt_number,
    },
    payment_intent_data={
      "application_fee_amount": fee_cents,
      "transfer_data": {"destination": account.stripe_account_id},
      "metadata": {
        "payment_scope": "order",
        "organization_id": organization_id,
        "order_id": order_id,
      },
    },
  )

  payment = OrderPayment(
    organization_id=organization_id,
    order_id=order_id,
    amount_cents=amount_cents,
    platform_fee_cents=fee_cents,
    net_amount_cents=net_cents,
    currency=settings.MARKETPLACE_CURRENCY.lower(),
    status=PAYMENT_STATUS_CHECKOUT_CREATED,
    stripe_checkout_session_id=str(_stripe_obj_get(checkout, "id")),
    stripe_payment_intent_id=(
      str(_stripe_obj_get(checkout, "payment_intent")) if _stripe_obj_get(checkout, "payment_intent") else None
    ),
    stripe_transfer_destination=account.stripe_account_id,
    receipt_number=receipt_number,
  )
  await repo.create_order_payment(session, payment)
  order.financial_status = PAYMENT_STATUS_AWAITING
  await session.flush()
  return OrderCheckoutSessionResponse(checkout_url=str(_stripe_obj_get(checkout, "url")), payment_id=payment.id)


async def get_finance_summary(
  session: AsyncSession,
  *,
  organization_id: str,
) -> MarketplaceFinanceSummary:
  account = await repo.get_connected_account(session, organization_id=organization_id)
  rows = await repo.list_payments_for_org(session, organization_id=organization_id)
  total_paid_cents = sum(
    payment.amount_cents for payment, _ in rows if payment.status in {PAYMENT_STATUS_PAID, PAYMENT_STATUS_PAYOUT_SENT}
  )
  total_platform_fee_cents = sum(
    payment.platform_fee_cents for payment, _ in rows if payment.status in {PAYMENT_STATUS_PAID, PAYMENT_STATUS_PAYOUT_SENT}
  )
  total_net_cents = sum(
    payment.net_amount_cents for payment, _ in rows if payment.status in {PAYMENT_STATUS_PAID, PAYMENT_STATUS_PAYOUT_SENT}
  )
  pending_payout_cents = sum(payment.net_amount_cents for payment, _ in rows if payment.status == PAYMENT_STATUS_PAID)
  disputed_cents = sum(payment.amount_cents for payment, _ in rows if payment.status == PAYMENT_STATUS_DISPUTED)
  refundable_cents = sum(
    payment.amount_cents for payment, _ in rows if payment.status in {PAYMENT_STATUS_PAID, PAYMENT_STATUS_PAYOUT_SENT}
  )
  return MarketplaceFinanceSummary(
    connected_account=_connected_account_out(organization_id, account),
    total_paid_cents=total_paid_cents,
    total_platform_fee_cents=total_platform_fee_cents,
    total_net_cents=total_net_cents,
    pending_payout_cents=pending_payout_cents,
    disputed_cents=disputed_cents,
    refundable_cents=refundable_cents,
    payments=[_payment_list_item(payment, order) for payment, order in rows],
  )


async def get_current_order_payment(
  session: AsyncSession,
  *,
  organization_id: str,
  order_id: str,
) -> OrderPaymentOut:
  order = await repo.get_order(session, order_id=order_id)
  if order is None or order.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="order not found")
  payment = await repo.get_current_payment(session, order_id=order_id)
  if payment is None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payment not found")
  return _payment_out(payment)


async def get_order_receipt(
  session: AsyncSession,
  *,
  organization_id: str,
  order_id: str,
) -> OrderReceiptOut:
  order = await repo.get_order(session, order_id=order_id)
  if order is None or order.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="order not found")
  payment = await repo.get_current_payment(session, order_id=order_id)
  if payment is None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payment not found")
  return OrderReceiptOut(
    receipt_number=payment.receipt_number,
    order_id=order.id,
    order_code=order.order_code,
    client_name=order.client_name,
    product_name=order.product_name,
    quantity=order.quantity,
    amount_cents=payment.amount_cents,
    platform_fee_cents=payment.platform_fee_cents,
    net_amount_cents=payment.net_amount_cents,
    currency=payment.currency,
    payment_status=payment.status,
    financial_status=order.financial_status,
    paid_at=payment.paid_at,
  )


async def mark_checkout_completed(
  session: AsyncSession,
  *,
  checkout_session_id: str,
  payment_intent_id: str | None,
  paid_at: datetime | None = None,
) -> None:
  payment = await repo.get_payment_by_checkout_session(session, checkout_session_id=checkout_session_id)
  if payment is None:
    return
  order = await repo.get_order(session, order_id=payment.order_id)
  if payment.status not in {PAYMENT_STATUS_PAYOUT_SENT, PAYMENT_STATUS_REFUNDED}:
    payment.status = PAYMENT_STATUS_PAID
  if payment_intent_id:
    payment.stripe_payment_intent_id = payment_intent_id
  payment.paid_at = paid_at or datetime.now(timezone.utc)
  if order is not None:
    if payment.status in {PAYMENT_STATUS_PAYOUT_SENT, PAYMENT_STATUS_REFUNDED}:
      order.financial_status = payment.status
    else:
      order.financial_status = PAYMENT_STATUS_PAID
  await session.flush()


async def mark_checkout_failed(
  session: AsyncSession,
  *,
  checkout_session_id: str,
  payment_error: str | None = None,
) -> None:
  payment = await repo.get_payment_by_checkout_session(session, checkout_session_id=checkout_session_id)
  if payment is None:
    return
  order = await repo.get_order(session, order_id=payment.order_id)
  payment.status = PAYMENT_STATUS_FAILED
  payment.payment_error = payment_error
  if order is not None:
    order.financial_status = PAYMENT_STATUS_FAILED
  await session.flush()


async def mark_charge_transfer_created(
  session: AsyncSession,
  *,
  payment_intent_id: str,
  order_id: str | None = None,
  payout_sent_at: datetime | None = None,
) -> None:
  payment = await repo.get_payment_by_payment_intent(session, payment_intent_id=payment_intent_id)
  if payment is None and order_id:
    payment = await repo.get_current_payment(session, order_id=order_id)
  if payment is None:
    return
  order = await repo.get_order(session, order_id=payment.order_id)
  payment.stripe_payment_intent_id = payment_intent_id
  payment.status = PAYMENT_STATUS_PAYOUT_SENT
  payment.payout_sent_at = payout_sent_at or datetime.now(timezone.utc)
  if order is not None:
    order.financial_status = PAYMENT_STATUS_PAYOUT_SENT
  await session.flush()


async def mark_payment_refunded(
  session: AsyncSession,
  *,
  payment_intent_id: str,
  order_id: str | None = None,
) -> None:
  payment = await repo.get_payment_by_payment_intent(session, payment_intent_id=payment_intent_id)
  if payment is None and order_id:
    payment = await repo.get_current_payment(session, order_id=order_id)
  if payment is None:
    return
  order = await repo.get_order(session, order_id=payment.order_id)
  payment.stripe_payment_intent_id = payment_intent_id
  payment.status = PAYMENT_STATUS_REFUNDED
  payment.refunded_at = datetime.now(timezone.utc)
  if order is not None:
    order.financial_status = PAYMENT_STATUS_REFUNDED
  await session.flush()


async def request_order_refund(
  session: AsyncSession,
  *,
  organization_id: str,
  order_id: str,
  reason: str = "requested_by_customer",
) -> OrderPaymentOut:
  order = await repo.get_order(session, order_id=order_id)
  if order is None or order.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="order not found")
  payment = await repo.get_current_payment(session, order_id=order_id)
  if payment is None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payment not found")
  if payment.status not in {PAYMENT_STATUS_PAID, PAYMENT_STATUS_PAYOUT_SENT}:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="payment is not refundable")
  if not payment.stripe_payment_intent_id:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="payment intent not available")

  _require_stripe()
  try:
    refund = stripe.Refund.create(
      payment_intent=payment.stripe_payment_intent_id,
      reason=reason,
      metadata={"organization_id": organization_id, "order_id": order_id, "payment_id": payment.id},
    )
  except Exception as exc:
    raise HTTPException(status_code=400, detail=f"unable to create refund: {exc}") from exc

  payment.status = PAYMENT_STATUS_REFUND_PENDING
  payment.stripe_refund_id = str(_stripe_obj_get(refund, "id"))
  payment.refund_reason = reason
  order.financial_status = PAYMENT_STATUS_REFUND_PENDING
  await session.flush()
  return _payment_out(payment)


async def mark_payment_disputed(
  session: AsyncSession,
  *,
  payment_intent_id: str,
  dispute_id: str,
  dispute_status: str,
  order_id: str | None = None,
  disputed_at: datetime | None = None,
) -> None:
  payment = await repo.get_payment_by_payment_intent(session, payment_intent_id=payment_intent_id)
  if payment is None and order_id:
    payment = await repo.get_current_payment(session, order_id=order_id)
  if payment is None:
    return
  order = await repo.get_order(session, order_id=payment.order_id)
  payment.stripe_payment_intent_id = payment_intent_id
  payment.stripe_dispute_id = dispute_id
  payment.dispute_status = dispute_status
  payment.disputed_at = disputed_at or datetime.now(timezone.utc)
  payment.status = PAYMENT_STATUS_DISPUTED
  if order is not None:
    order.financial_status = PAYMENT_STATUS_DISPUTED
  await session.flush()
