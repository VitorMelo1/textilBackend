from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from urllib.parse import urlencode
from uuid import uuid4

import httpx
from fastapi import HTTPException, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import get_settings
from shared.db.models import MercadoPagoConnectedAccount, Order, OrderPayment, StripeConnectedAccount

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

MERCADO_PAGO_PROVIDER_DESTINATION = "mercado_pago"
MERCADO_PAGO_STATE_SALT = "mercado-pago-oauth"


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


def _require_mercado_pago_oauth_settings():
  settings = get_settings()
  missing = [
    key
    for key in ("MERCADO_PAGO_CLIENT_ID", "MERCADO_PAGO_CLIENT_SECRET", "MERCADO_PAGO_REDIRECT_URI")
    if not getattr(settings, key)
  ]
  if missing:
    raise HTTPException(status_code=503, detail=f"mercado pago not configured: {', '.join(missing)}")
  return settings


def _mercado_pago_base_url() -> str:
  return get_settings().MERCADO_PAGO_API_BASE_URL.rstrip("/")


def _mercado_pago_headers(access_token: str) -> dict[str, str]:
  return {
    "accept": "application/json",
    "content-type": "application/json",
    "Authorization": f"Bearer {access_token}",
  }


def _mp_money(cents: int) -> float:
  return float((Decimal(cents) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _raise_mp_error(response: httpx.Response, fallback: str) -> None:
  if response.status_code < 400:
    return
  try:
    payload = response.json()
  except ValueError:
    payload = response.text
  raise HTTPException(status_code=400, detail=f"{fallback}: {payload}")


def _state_serializer() -> URLSafeTimedSerializer:
  settings = get_settings()
  secret = settings.SESSION_SECRET or settings.JWT_SECRET
  return URLSafeTimedSerializer(secret_key=secret, salt=MERCADO_PAGO_STATE_SALT)


def _encode_oauth_state(*, organization_id: str, return_url: str | None, refresh_url: str | None) -> str:
  return _state_serializer().dumps(
    {"organization_id": organization_id, "return_url": return_url, "refresh_url": refresh_url}
  )


def _decode_oauth_state(state: str) -> dict[str, str | None]:
  try:
    payload = _state_serializer().loads(state, max_age=60 * 30)
  except SignatureExpired as exc:
    raise HTTPException(status_code=400, detail="mercado pago oauth state expired") from exc
  except BadSignature as exc:
    raise HTTPException(status_code=400, detail="invalid mercado pago oauth state") from exc
  if not isinstance(payload, dict) or not payload.get("organization_id"):
    raise HTTPException(status_code=400, detail="invalid mercado pago oauth state")
  return payload


def _parse_mp_datetime(value: str | None) -> datetime | None:
  if not value:
    return None
  try:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
  except ValueError:
    return None


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


def _connected_account_out(
  organization_id: str,
  account: MercadoPagoConnectedAccount | StripeConnectedAccount | None,
) -> ConnectedAccountOut:
  if account is None:
    return ConnectedAccountOut(organization_id=organization_id)
  if isinstance(account, MercadoPagoConnectedAccount) or hasattr(account, "mp_user_id"):
    return ConnectedAccountOut(
      organization_id=account.organization_id,
      provider="mercado_pago",
      mercado_pago_user_id=account.mp_user_id,
      mercado_pago_public_key=account.public_key,
      onboarding_status=account.onboarding_status,
      charges_enabled=bool(account.access_token and account.onboarding_status == "connected"),
      payouts_enabled=bool(account.access_token and account.onboarding_status == "connected"),
      details_submitted=bool(account.access_token and account.onboarding_status == "connected"),
      default_currency=account.default_currency,
    )
  return ConnectedAccountOut(
    organization_id=account.organization_id,
    provider="stripe",
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
    mercado_pago_preference_id=getattr(payment, "mercado_pago_preference_id", None),
    mercado_pago_payment_id=getattr(payment, "mercado_pago_payment_id", None),
    mercado_pago_status_detail=getattr(payment, "mercado_pago_status_detail", None),
    mercado_pago_refund_id=getattr(payment, "mercado_pago_refund_id", None),
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


def _account_ready(account: MercadoPagoConnectedAccount) -> bool:
  return bool(account.access_token and account.onboarding_status == "connected")


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
  account = await repo.get_connected_account(session, organization_id=organization_id)
  return _connected_account_out(organization_id, account)


async def create_onboarding_link(
  session: AsyncSession,
  *,
  organization_id: str,
  return_url: str | None,
  refresh_url: str | None,
) -> str:
  settings = _require_mercado_pago_oauth_settings()
  state = _encode_oauth_state(organization_id=organization_id, return_url=return_url, refresh_url=refresh_url)
  params = {
    "client_id": settings.MERCADO_PAGO_CLIENT_ID,
    "response_type": "code",
    "platform_id": "mp",
    "redirect_uri": settings.MERCADO_PAGO_REDIRECT_URI,
    "state": state,
  }
  return f"{settings.MERCADO_PAGO_AUTH_URL}?{urlencode(params)}"


async def handle_mercado_pago_oauth_callback(
  session: AsyncSession,
  *,
  code: str,
  state: str,
) -> str:
  settings = _require_mercado_pago_oauth_settings()
  state_payload = _decode_oauth_state(state)
  organization_id = str(state_payload["organization_id"])
  return_url = state_payload.get("return_url") or settings.STRIPE_CONNECT_RETURN_URL or settings.CORE_API_BASE_URL

  token_payload = {
    "client_secret": settings.MERCADO_PAGO_CLIENT_SECRET,
    "client_id": settings.MERCADO_PAGO_CLIENT_ID,
    "grant_type": "authorization_code",
    "code": code,
    "redirect_uri": settings.MERCADO_PAGO_REDIRECT_URI,
  }
  async with httpx.AsyncClient(timeout=20) as client:
    response = await client.post(
      f"{_mercado_pago_base_url()}/oauth/token",
      data=token_payload,
      headers={"accept": "application/json", "content-type": "application/x-www-form-urlencoded"},
    )
  _raise_mp_error(response, "unable to exchange mercado pago oauth code")
  data = response.json()

  mp_user_id = str(data.get("user_id") or data.get("collector_id") or "")
  access_token = data.get("access_token")
  if not mp_user_id or not access_token:
    raise HTTPException(status_code=400, detail="mercado pago oauth response missing seller account data")

  expires_in = int(data.get("expires_in") or 0)
  token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in) if expires_in > 0 else None
  existing = await repo.get_connected_account(session, organization_id=organization_id)
  row = existing or MercadoPagoConnectedAccount(organization_id=organization_id, mp_user_id=mp_user_id, access_token=access_token)
  row.mp_user_id = mp_user_id
  row.access_token = str(access_token)
  row.refresh_token = data.get("refresh_token")
  row.public_key = data.get("public_key")
  row.token_expires_at = token_expires_at
  row.onboarding_status = "connected"
  row.live_mode = bool(data.get("live_mode", False))
  row.default_currency = str(data.get("default_currency_id") or settings.MARKETPLACE_CURRENCY).lower()
  if existing is None:
    await repo.create_connected_account(session, row)
  await session.flush()
  return str(return_url)


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
  return _connected_account_out(organization_id, account)


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
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="mercado pago account not connected")
  if not _account_ready(account):
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="mercado pago account is not ready to receive payments")

  amount_cents = _order_amount_cents(order)
  if amount_cents <= 0:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="order amount must be greater than zero")

  current = await repo.get_current_payment(session, order_id=order_id)
  if current is not None and current.status == PAYMENT_STATUS_PAID:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="order already paid")

  settings = get_settings()
  fee_cents = calculate_platform_fee_cents(amount_cents)
  net_cents = max(amount_cents - fee_cents, 0)
  receipt_number = f"REC-{order.order_code}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

  payment = OrderPayment(
    organization_id=organization_id,
    order_id=order_id,
    amount_cents=amount_cents,
    platform_fee_cents=fee_cents,
    net_amount_cents=net_cents,
    currency=settings.MARKETPLACE_CURRENCY.lower(),
    status=PAYMENT_STATUS_CHECKOUT_CREATED,
    stripe_transfer_destination=MERCADO_PAGO_PROVIDER_DESTINATION,
    receipt_number=receipt_number,
  )
  await repo.create_order_payment(session, payment)

  webhook_base = settings.MERCADO_PAGO_WEBHOOK_URL or f"{settings.CORE_API_BASE_URL.rstrip('/')}/marketplace/mercado-pago/webhook"
  separator = "&" if "?" in webhook_base else "?"
  notification_url = f"{webhook_base}{separator}payment_id={payment.id}"
  preference_payload: dict[str, Any] = {
    "items": [
      {
        "id": order.id,
        "title": f"{order.order_code} - {order.product_name}",
        "currency_id": settings.MARKETPLACE_CURRENCY.upper(),
        "quantity": 1,
        "unit_price": _mp_money(amount_cents),
      }
    ],
    "marketplace_fee": _mp_money(fee_cents),
    "external_reference": payment.id,
    "notification_url": notification_url,
    "back_urls": {"success": success_url, "failure": cancel_url, "pending": cancel_url},
    "auto_return": "approved",
    "metadata": {"organization_id": organization_id, "order_id": order_id, "payment_id": payment.id},
  }
  async with httpx.AsyncClient(timeout=20) as client:
    response = await client.post(
      f"{_mercado_pago_base_url()}/checkout/preferences",
      headers={**_mercado_pago_headers(account.access_token), "X-Idempotency-Key": str(uuid4())},
      json=preference_payload,
    )
  _raise_mp_error(response, "unable to create mercado pago checkout preference")
  preference = response.json()
  checkout_url = (
    preference.get("sandbox_init_point") if settings.MERCADO_PAGO_USE_SANDBOX_CHECKOUT else preference.get("init_point")
  ) or preference.get("init_point") or preference.get("sandbox_init_point")
  if not checkout_url:
    raise HTTPException(status_code=400, detail="mercado pago preference response missing checkout url")

  payment.mercado_pago_preference_id = str(preference.get("id"))
  order.financial_status = PAYMENT_STATUS_AWAITING
  await session.flush()
  return OrderCheckoutSessionResponse(checkout_url=str(checkout_url), payment_id=payment.id)


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


async def process_mercado_pago_webhook(
  session: AsyncSession,
  *,
  payment_id: str | None = None,
  mercado_pago_payment_id: str | None = None,
) -> None:
  payment = await repo.get_payment(session, payment_id=payment_id) if payment_id else None
  if payment is None and mercado_pago_payment_id:
    payment = await repo.get_payment_by_mercado_pago_payment_id(
      session, mercado_pago_payment_id=mercado_pago_payment_id
    )
  if payment is None:
    return

  account = await repo.get_connected_account(session, organization_id=payment.organization_id)
  if account is None:
    return

  if mercado_pago_payment_id is None:
    mercado_pago_payment_id = payment.mercado_pago_payment_id
  if mercado_pago_payment_id is None:
    return

  async with httpx.AsyncClient(timeout=20) as client:
    response = await client.get(
      f"{_mercado_pago_base_url()}/v1/payments/{mercado_pago_payment_id}",
      headers=_mercado_pago_headers(account.access_token),
    )
  _raise_mp_error(response, "unable to fetch mercado pago payment")
  mp_payment = response.json()

  order = await repo.get_order(session, order_id=payment.order_id)
  payment.mercado_pago_payment_id = str(mp_payment.get("id") or mercado_pago_payment_id)
  payment.mercado_pago_status_detail = mp_payment.get("status_detail")
  payment_error = mp_payment.get("status_detail") or mp_payment.get("status")
  status_value = str(mp_payment.get("status") or "").lower()

  if status_value == "approved":
    if payment.status not in {PAYMENT_STATUS_PAYOUT_SENT, PAYMENT_STATUS_REFUNDED}:
      payment.status = PAYMENT_STATUS_PAID
    payment.paid_at = _parse_mp_datetime(mp_payment.get("date_approved")) or datetime.now(timezone.utc)
    if order is not None:
      order.financial_status = payment.status if payment.status == PAYMENT_STATUS_PAYOUT_SENT else PAYMENT_STATUS_PAID
  elif status_value in {"refunded", "partially_refunded"}:
    payment.status = PAYMENT_STATUS_REFUNDED
    payment.refunded_at = datetime.now(timezone.utc)
    if order is not None:
      order.financial_status = PAYMENT_STATUS_REFUNDED
  elif status_value == "charged_back":
    payment.status = PAYMENT_STATUS_DISPUTED
    payment.dispute_status = payment_error
    payment.disputed_at = datetime.now(timezone.utc)
    if order is not None:
      order.financial_status = PAYMENT_STATUS_DISPUTED
  elif status_value in {"rejected"}:
    payment.status = PAYMENT_STATUS_FAILED
    payment.payment_error = payment_error
    if order is not None:
      order.financial_status = PAYMENT_STATUS_FAILED
  elif status_value in {"cancelled", "canceled"}:
    payment.status = PAYMENT_STATUS_CANCELLED
    payment.payment_error = payment_error
    if order is not None:
      order.financial_status = PAYMENT_STATUS_CANCELLED

  await session.flush()


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
  if not payment.mercado_pago_payment_id:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="mercado pago payment id not available")

  account = await repo.get_connected_account(session, organization_id=organization_id)
  if account is None:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="mercado pago account not connected")

  async with httpx.AsyncClient(timeout=20) as client:
    response = await client.post(
      f"{_mercado_pago_base_url()}/v1/payments/{payment.mercado_pago_payment_id}/refunds",
      headers={**_mercado_pago_headers(account.access_token), "X-Idempotency-Key": str(uuid4())},
      json={},
    )
  _raise_mp_error(response, "unable to create mercado pago refund")
  refund = response.json()

  payment.status = PAYMENT_STATUS_REFUND_PENDING
  payment.mercado_pago_refund_id = str(refund.get("id") or "")
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
