from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException

from app.entities.marketplace_payments import service


class FakeMpResponse:
  def __init__(self, payload: dict, status_code: int = 200) -> None:
    self._payload = payload
    self.status_code = status_code
    self.text = str(payload)

  def json(self) -> dict:
    return self._payload


class FakeMpClient:
  posts: list[dict] = []
  gets: list[dict] = []
  post_response = FakeMpResponse({"id": "pref_123", "init_point": "https://checkout.mercadopago.test/pref_123"})
  get_response = FakeMpResponse({"id": "mp_pay_123", "status": "approved", "status_detail": "accredited"})

  def __init__(self, *args, **kwargs) -> None:
    pass

  async def __aenter__(self):
    return self

  async def __aexit__(self, exc_type, exc, tb) -> None:
    return None

  async def post(self, url: str, **kwargs):
    self.posts.append({"url": url, **kwargs})
    return self.post_response

  async def get(self, url: str, **kwargs):
    self.gets.append({"url": url, **kwargs})
    return self.get_response


def mp_settings(**overrides):
  data = {
    "MARKETPLACE_CURRENCY": "brl",
    "PLATFORM_FEE_PERCENT": 10.0,
    "PLATFORM_FEE_MIN_CENTS": 200,
    "CORE_API_BASE_URL": "https://api.duonekso.test",
    "MERCADO_PAGO_WEBHOOK_URL": None,
    "MERCADO_PAGO_API_BASE_URL": "https://api.mercadopago.test",
    "MERCADO_PAGO_USE_SANDBOX_CHECKOUT": False,
    "MERCADO_PAGO_CLIENT_ID": "client-id",
    "MERCADO_PAGO_CLIENT_SECRET": "client-secret",
    "MERCADO_PAGO_REDIRECT_URI": "https://api.duonekso.test/marketplace/mercado-pago/oauth/callback",
    "MERCADO_PAGO_AUTH_URL": "https://auth.mercadopago.test/authorization",
    "SESSION_SECRET": "x" * 40,
    "JWT_SECRET": "y" * 40,
    "STRIPE_CONNECT_RETURN_URL": None,
  }
  data.update(overrides)
  return SimpleNamespace(**data)


def test_calculate_platform_fee_uses_percentage_with_minimum() -> None:
  assert service.calculate_platform_fee_cents(10_000) == 1_000
  assert service.calculate_platform_fee_cents(1_000) == 200


@pytest.mark.asyncio
async def test_create_onboarding_link_builds_mercado_pago_oauth_url() -> None:
  with patch("app.entities.marketplace_payments.service.get_settings", return_value=mp_settings()):
    url = await service.create_onboarding_link(
      AsyncMock(),
      organization_id="org-1",
      return_url="https://app.test/dashboard/finance",
      refresh_url="https://app.test/dashboard/finance",
    )

  parsed = urlparse(url)
  params = parse_qs(parsed.query)
  assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == "https://auth.mercadopago.test/authorization"
  assert params["client_id"] == ["client-id"]
  assert params["response_type"] == ["code"]
  assert params["redirect_uri"] == ["https://api.duonekso.test/marketplace/mercado-pago/oauth/callback"]
  assert params["state"][0]


@pytest.mark.asyncio
async def test_handle_oauth_callback_stores_mercado_pago_seller_token() -> None:
  session = AsyncMock()
  saved_rows = []
  settings = mp_settings()
  FakeMpClient.posts = []
  FakeMpClient.post_response = FakeMpResponse(
    {
      "user_id": 123456,
      "access_token": "seller-access-token",
      "refresh_token": "seller-refresh-token",
      "public_key": "APP_USR-public",
      "expires_in": 3600,
      "live_mode": True,
    }
  )
  with (
    patch("app.entities.marketplace_payments.service.get_settings", return_value=settings),
    patch("app.entities.marketplace_payments.service.repo.get_connected_account", new=AsyncMock(return_value=None)),
    patch(
      "app.entities.marketplace_payments.service.repo.create_connected_account",
      new=AsyncMock(side_effect=lambda _, row: saved_rows.append(row) or row),
    ),
    patch("app.entities.marketplace_payments.service.httpx.AsyncClient", FakeMpClient),
  ):
    state = service._encode_oauth_state(
      organization_id="org-1",
      return_url="https://app.test/dashboard/finance",
      refresh_url="https://app.test/dashboard/finance",
    )
    redirect = await service.handle_mercado_pago_oauth_callback(session, code="oauth-code", state=state)

  assert redirect == "https://app.test/dashboard/finance"
  assert FakeMpClient.posts[0]["url"] == "https://api.mercadopago.test/oauth/token"
  assert FakeMpClient.posts[0]["data"]["code"] == "oauth-code"
  assert saved_rows[0].organization_id == "org-1"
  assert saved_rows[0].mp_user_id == "123456"
  assert saved_rows[0].access_token == "seller-access-token"
  assert saved_rows[0].onboarding_status == "connected"


@pytest.mark.asyncio
async def test_create_order_checkout_session_creates_mercado_pago_preference_with_marketplace_fee() -> None:
  session = AsyncMock()
  order = SimpleNamespace(
    id="order-1",
    organization_id="org-1",
    order_code="PED-1",
    product_name="Camiseta",
    quantity=10,
    unit_price=12.5,
    financial_status="awaiting_payment",
  )
  account = SimpleNamespace(
    organization_id="org-1",
    mp_user_id="seller_123",
    access_token="seller-token",
    onboarding_status="connected",
    public_key="APP_USR-public",
    default_currency="brl",
  )

  async def persist_payment(_, row):
    row.id = "pay-1"
    return row

  FakeMpClient.posts = []
  FakeMpClient.post_response = FakeMpResponse(
    {"id": "pref_123", "init_point": "https://checkout.mercadopago.test/pref_123"}
  )

  with (
    patch("app.entities.marketplace_payments.service.repo.get_order", new=AsyncMock(return_value=order)),
    patch("app.entities.marketplace_payments.service.repo.get_connected_account", new=AsyncMock(return_value=account)),
    patch("app.entities.marketplace_payments.service.repo.get_current_payment", new=AsyncMock(return_value=None)),
    patch("app.entities.marketplace_payments.service.repo.create_order_payment", new=AsyncMock(side_effect=persist_payment)) as create_payment,
    patch("app.entities.marketplace_payments.service.get_settings", return_value=mp_settings()),
    patch("app.entities.marketplace_payments.service.httpx.AsyncClient", FakeMpClient),
  ):
    result = await service.create_order_checkout_session(
      session,
      organization_id="org-1",
      order_id="order-1",
      success_url="https://app.test/success",
      cancel_url="https://app.test/cancel",
    )

  assert result.checkout_url == "https://checkout.mercadopago.test/pref_123"
  assert result.payment_id == "pay-1"
  mp_call = FakeMpClient.posts[0]
  assert mp_call["url"] == "https://api.mercadopago.test/checkout/preferences"
  assert mp_call["headers"]["Authorization"] == "Bearer seller-token"
  assert mp_call["json"]["marketplace_fee"] == 12.5
  assert mp_call["json"]["external_reference"] == "pay-1"
  assert mp_call["json"]["items"][0]["unit_price"] == 125.0
  assert mp_call["json"]["notification_url"] == "https://api.duonekso.test/marketplace/mercado-pago/webhook?payment_id=pay-1"
  create_payment.assert_awaited_once()
  saved = create_payment.await_args.args[1]
  assert saved.amount_cents == 12_500
  assert saved.platform_fee_cents == 1_250
  assert saved.mercado_pago_preference_id == "pref_123"
  assert saved.stripe_transfer_destination == "mercado_pago"
  assert saved.status == "checkout_created"


@pytest.mark.asyncio
async def test_create_order_checkout_session_requires_connected_mercado_pago_account() -> None:
  session = AsyncMock()
  order = SimpleNamespace(
    id="order-1",
    organization_id="org-1",
    order_code="PED-1",
    product_name="Camiseta",
    quantity=10,
    unit_price=12.5,
    financial_status="awaiting_payment",
  )
  account = SimpleNamespace(
    access_token=None,
    onboarding_status="not_started",
  )

  with (
    patch("app.entities.marketplace_payments.service.repo.get_order", new=AsyncMock(return_value=order)),
    patch("app.entities.marketplace_payments.service.repo.get_connected_account", new=AsyncMock(return_value=account)),
    patch("app.entities.marketplace_payments.service.repo.get_current_payment", new=AsyncMock(return_value=None)),
  ):
    with pytest.raises(HTTPException) as exc:
      await service.create_order_checkout_session(
        session,
        organization_id="org-1",
        order_id="order-1",
        success_url="https://app.test/success",
        cancel_url="https://app.test/cancel",
      )

  assert exc.value.status_code == 409
  assert exc.value.detail == "mercado pago account is not ready to receive payments"


@pytest.mark.asyncio
async def test_create_order_checkout_session_requires_mercado_pago_account() -> None:
  session = AsyncMock()
  order = SimpleNamespace(
    id="order-1",
    organization_id="org-1",
    order_code="PED-1",
    product_name="Camiseta",
    quantity=10,
    unit_price=12.5,
    financial_status="awaiting_payment",
  )
  with (
    patch("app.entities.marketplace_payments.service.repo.get_order", new=AsyncMock(return_value=order)),
    patch("app.entities.marketplace_payments.service.repo.get_connected_account", new=AsyncMock(return_value=None)),
  ):
    with pytest.raises(HTTPException) as exc:
      await service.create_order_checkout_session(
        session,
        organization_id="org-1",
        order_id="order-1",
        success_url="https://app.test/success",
        cancel_url="https://app.test/cancel",
      )

  assert exc.value.status_code == 409
  assert exc.value.detail == "mercado pago account not connected"


@pytest.mark.asyncio
async def test_mark_checkout_completed_updates_payment_and_order() -> None:
  session = AsyncMock()
  payment = SimpleNamespace(
    id="pay-1",
    order_id="order-1",
    status="checkout_created",
    stripe_payment_intent_id=None,
    paid_at=None,
  )
  order = SimpleNamespace(id="order-1", financial_status="awaiting_payment")
  paid_at = datetime(2026, 7, 1, tzinfo=timezone.utc)

  with (
    patch("app.entities.marketplace_payments.service.repo.get_payment_by_checkout_session", new=AsyncMock(return_value=payment)),
    patch("app.entities.marketplace_payments.service.repo.get_order", new=AsyncMock(return_value=order)),
  ):
    await service.mark_checkout_completed(
      session,
      checkout_session_id="cs_123",
      payment_intent_id="pi_123",
      paid_at=paid_at,
    )

  assert payment.status == "paid"
  assert payment.stripe_payment_intent_id == "pi_123"
  assert payment.paid_at == paid_at
  assert order.financial_status == "paid"


@pytest.mark.asyncio
async def test_mark_checkout_completed_does_not_downgrade_payout_sent() -> None:
  session = AsyncMock()
  payment = SimpleNamespace(
    id="pay-1",
    order_id="order-1",
    status="payout_sent",
    stripe_payment_intent_id="pi_123",
    paid_at=None,
  )
  order = SimpleNamespace(id="order-1", financial_status="payout_sent")
  paid_at = datetime(2026, 7, 1, tzinfo=timezone.utc)

  with (
    patch("app.entities.marketplace_payments.service.repo.get_payment_by_checkout_session", new=AsyncMock(return_value=payment)),
    patch("app.entities.marketplace_payments.service.repo.get_order", new=AsyncMock(return_value=order)),
  ):
    await service.mark_checkout_completed(
      session,
      checkout_session_id="cs_123",
      payment_intent_id="pi_123",
      paid_at=paid_at,
    )

  assert payment.status == "payout_sent"
  assert payment.paid_at == paid_at
  assert order.financial_status == "payout_sent"


@pytest.mark.asyncio
async def test_mark_charge_transfer_created_marks_payout_sent() -> None:
  session = AsyncMock()
  payment = SimpleNamespace(
    id="pay-1",
    order_id="order-1",
    status="paid",
    stripe_payment_intent_id="pi_123",
    payout_sent_at=None,
  )
  order = SimpleNamespace(id="order-1", financial_status="paid")
  payout_at = datetime(2026, 7, 1, tzinfo=timezone.utc)

  with (
    patch("app.entities.marketplace_payments.service.repo.get_payment_by_payment_intent", new=AsyncMock(return_value=payment)),
    patch("app.entities.marketplace_payments.service.repo.get_order", new=AsyncMock(return_value=order)),
  ):
    await service.mark_charge_transfer_created(
      session,
      payment_intent_id="pi_123",
      payout_sent_at=payout_at,
    )

  assert payment.status == "payout_sent"
  assert payment.payout_sent_at == payout_at
  assert order.financial_status == "payout_sent"


@pytest.mark.asyncio
async def test_mark_charge_transfer_created_falls_back_to_order_id_when_intent_not_saved() -> None:
  session = AsyncMock()
  payment = SimpleNamespace(
    id="pay-1",
    order_id="order-1",
    status="checkout_created",
    stripe_payment_intent_id=None,
    payout_sent_at=None,
  )
  order = SimpleNamespace(id="order-1", financial_status="awaiting_payment")

  with (
    patch("app.entities.marketplace_payments.service.repo.get_payment_by_payment_intent", new=AsyncMock(return_value=None)),
    patch("app.entities.marketplace_payments.service.repo.get_current_payment", new=AsyncMock(return_value=payment)),
    patch("app.entities.marketplace_payments.service.repo.get_order", new=AsyncMock(return_value=order)),
  ):
    await service.mark_charge_transfer_created(
      session,
      payment_intent_id="pi_123",
      order_id="order-1",
    )

  assert payment.stripe_payment_intent_id == "pi_123"
  assert payment.status == "payout_sent"
  assert order.financial_status == "payout_sent"


@pytest.mark.asyncio
async def test_mark_payment_refunded_updates_payment_and_order() -> None:
  session = AsyncMock()
  payment = SimpleNamespace(id="pay-1", order_id="order-1", status="paid", stripe_payment_intent_id="pi_123")
  order = SimpleNamespace(id="order-1", financial_status="paid")

  with (
    patch("app.entities.marketplace_payments.service.repo.get_payment_by_payment_intent", new=AsyncMock(return_value=payment)),
    patch("app.entities.marketplace_payments.service.repo.get_order", new=AsyncMock(return_value=order)),
  ):
    await service.mark_payment_refunded(session, payment_intent_id="pi_123")

  assert payment.status == "refunded"
  assert order.financial_status == "refunded"


@pytest.mark.asyncio
async def test_mark_payment_refunded_falls_back_to_order_id_when_intent_not_saved() -> None:
  session = AsyncMock()
  payment = SimpleNamespace(id="pay-1", order_id="order-1", status="paid", stripe_payment_intent_id=None)
  order = SimpleNamespace(id="order-1", financial_status="paid")

  with (
    patch("app.entities.marketplace_payments.service.repo.get_payment_by_payment_intent", new=AsyncMock(return_value=None)),
    patch("app.entities.marketplace_payments.service.repo.get_current_payment", new=AsyncMock(return_value=payment)),
    patch("app.entities.marketplace_payments.service.repo.get_order", new=AsyncMock(return_value=order)),
  ):
    await service.mark_payment_refunded(
      session,
      payment_intent_id="pi_123",
      order_id="order-1",
    )

  assert payment.stripe_payment_intent_id == "pi_123"
  assert payment.status == "refunded"
  assert order.financial_status == "refunded"


@pytest.mark.asyncio
async def test_request_order_refund_creates_mercado_pago_refund_and_marks_pending() -> None:
  session = AsyncMock()
  order = SimpleNamespace(id="order-1", organization_id="org-1", financial_status="paid")
  payment = SimpleNamespace(
    id="pay-1",
    organization_id="org-1",
    order_id="order-1",
    status="paid",
    amount_cents=12_500,
    platform_fee_cents=1_250,
    net_amount_cents=11_250,
    currency="brl",
    receipt_number="REC-PED-1",
    stripe_payment_intent_id="pi_123",
    mercado_pago_preference_id="pref_123",
    mercado_pago_payment_id="mp_pay_123",
    mercado_pago_status_detail="accredited",
    mercado_pago_refund_id=None,
    stripe_refund_id=None,
    refund_reason=None,
    refunded_at=None,
    stripe_dispute_id=None,
    dispute_status=None,
    disputed_at=None,
    payment_error=None,
    paid_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
    payout_sent_at=None,
  )
  account = SimpleNamespace(access_token="seller-token")
  FakeMpClient.posts = []
  FakeMpClient.post_response = FakeMpResponse({"id": "mp_ref_123"})

  with (
    patch("app.entities.marketplace_payments.service.repo.get_order", new=AsyncMock(return_value=order)),
    patch("app.entities.marketplace_payments.service.repo.get_current_payment", new=AsyncMock(return_value=payment)),
    patch("app.entities.marketplace_payments.service.repo.get_connected_account", new=AsyncMock(return_value=account)),
    patch("app.entities.marketplace_payments.service.get_settings", return_value=mp_settings()),
    patch("app.entities.marketplace_payments.service.httpx.AsyncClient", FakeMpClient),
  ):
    result = await service.request_order_refund(
      session,
      organization_id="org-1",
      order_id="order-1",
      reason="requested_by_customer",
    )

  assert FakeMpClient.posts[0]["url"] == "https://api.mercadopago.test/v1/payments/mp_pay_123/refunds"
  assert FakeMpClient.posts[0]["headers"]["Authorization"] == "Bearer seller-token"
  assert result.status == "refund_pending"
  assert payment.status == "refund_pending"
  assert payment.mercado_pago_refund_id == "mp_ref_123"
  assert order.financial_status == "refund_pending"


@pytest.mark.asyncio
async def test_process_mercado_pago_webhook_marks_approved_payment_paid() -> None:
  session = AsyncMock()
  payment = SimpleNamespace(
    id="pay-1",
    organization_id="org-1",
    order_id="order-1",
    status="checkout_created",
    mercado_pago_payment_id=None,
    mercado_pago_status_detail=None,
    paid_at=None,
  )
  order = SimpleNamespace(id="order-1", financial_status="awaiting_payment")
  account = SimpleNamespace(access_token="seller-token")
  FakeMpClient.gets = []
  FakeMpClient.get_response = FakeMpResponse(
    {
      "id": "mp_pay_123",
      "status": "approved",
      "status_detail": "accredited",
      "date_approved": "2026-07-01T12:00:00.000-03:00",
    }
  )

  with (
    patch("app.entities.marketplace_payments.service.repo.get_payment", new=AsyncMock(return_value=payment)),
    patch("app.entities.marketplace_payments.service.repo.get_connected_account", new=AsyncMock(return_value=account)),
    patch("app.entities.marketplace_payments.service.repo.get_order", new=AsyncMock(return_value=order)),
    patch("app.entities.marketplace_payments.service.get_settings", return_value=mp_settings()),
    patch("app.entities.marketplace_payments.service.httpx.AsyncClient", FakeMpClient),
  ):
    await service.process_mercado_pago_webhook(
      session,
      payment_id="pay-1",
      mercado_pago_payment_id="mp_pay_123",
    )

  assert FakeMpClient.gets[0]["url"] == "https://api.mercadopago.test/v1/payments/mp_pay_123"
  assert payment.status == "paid"
  assert payment.mercado_pago_payment_id == "mp_pay_123"
  assert payment.mercado_pago_status_detail == "accredited"
  assert order.financial_status == "paid"


@pytest.mark.asyncio
async def test_mark_payment_disputed_updates_payment_and_order() -> None:
  session = AsyncMock()
  payment = SimpleNamespace(
    id="pay-1",
    order_id="order-1",
    status="payout_sent",
    stripe_payment_intent_id="pi_123",
    stripe_dispute_id=None,
    dispute_status=None,
    disputed_at=None,
  )
  order = SimpleNamespace(id="order-1", financial_status="payout_sent")
  disputed_at = datetime(2026, 7, 1, tzinfo=timezone.utc)

  with (
    patch("app.entities.marketplace_payments.service.repo.get_payment_by_payment_intent", new=AsyncMock(return_value=payment)),
    patch("app.entities.marketplace_payments.service.repo.get_order", new=AsyncMock(return_value=order)),
  ):
    await service.mark_payment_disputed(
      session,
      payment_intent_id="pi_123",
      dispute_id="dp_123",
      dispute_status="needs_response",
      disputed_at=disputed_at,
    )

  assert payment.status == "disputed"
  assert payment.stripe_dispute_id == "dp_123"
  assert payment.dispute_status == "needs_response"
  assert payment.disputed_at == disputed_at
  assert order.financial_status == "disputed"
