from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException

from app.entities.marketplace_payments import service


def test_calculate_platform_fee_uses_percentage_with_minimum() -> None:
  assert service.calculate_platform_fee_cents(10_000) == 1_000
  assert service.calculate_platform_fee_cents(1_000) == 200


@pytest.mark.asyncio
async def test_create_order_checkout_session_uses_destination_charge() -> None:
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
    stripe_account_id="acct_123",
    charges_enabled=True,
    payouts_enabled=True,
    details_submitted=True,
  )
  checkout = SimpleNamespace(id="cs_123", url="https://checkout.stripe.test/cs_123", payment_intent="pi_123")
  settings = SimpleNamespace(STRIPE_SECRET_KEY="sk_test", MARKETPLACE_CURRENCY="brl")

  with (
    patch("app.entities.marketplace_payments.service.repo.get_order", new=AsyncMock(return_value=order)),
    patch("app.entities.marketplace_payments.service.repo.get_connected_account", new=AsyncMock(return_value=account)),
    patch("app.entities.marketplace_payments.service.repo.get_current_payment", new=AsyncMock(return_value=None)),
    patch("app.entities.marketplace_payments.service.repo.create_order_payment", new=AsyncMock()) as create_payment,
    patch("app.entities.marketplace_payments.service._require_stripe", return_value=settings),
  ):
    service.stripe = Mock()
    service.stripe.checkout.Session.create.return_value = checkout

    result = await service.create_order_checkout_session(
      session,
      organization_id="org-1",
      order_id="order-1",
      success_url="https://app.test/success",
      cancel_url="https://app.test/cancel",
    )

  assert result.checkout_url == "https://checkout.stripe.test/cs_123"
  stripe_kwargs = service.stripe.checkout.Session.create.call_args.kwargs
  assert stripe_kwargs["mode"] == "payment"
  assert stripe_kwargs["payment_intent_data"]["application_fee_amount"] == 1_250
  assert stripe_kwargs["payment_intent_data"]["transfer_data"]["destination"] == "acct_123"
  assert stripe_kwargs["metadata"]["payment_scope"] == "order"
  create_payment.assert_awaited_once()
  saved = create_payment.await_args.args[1]
  assert saved.amount_cents == 12_500
  assert saved.platform_fee_cents == 1_250
  assert saved.status == "checkout_created"


@pytest.mark.asyncio
async def test_create_order_checkout_session_requires_onboarded_account() -> None:
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
    stripe_account_id="acct_123",
    charges_enabled=False,
    payouts_enabled=True,
    details_submitted=True,
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
  assert exc.value.detail == "connected account is not ready to receive payments"


@pytest.mark.asyncio
async def test_create_order_checkout_session_requires_payouts_and_details() -> None:
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
    stripe_account_id="acct_123",
    charges_enabled=True,
    payouts_enabled=False,
    details_submitted=False,
  )

  with (
    patch("app.entities.marketplace_payments.service.repo.get_order", new=AsyncMock(return_value=order)),
    patch("app.entities.marketplace_payments.service.repo.get_connected_account", new=AsyncMock(return_value=account)),
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
  assert exc.value.detail == "connected account is not ready to receive payments"


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
async def test_request_order_refund_creates_stripe_refund_and_marks_pending() -> None:
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
  refund = SimpleNamespace(id="re_123")

  with (
    patch("app.entities.marketplace_payments.service.repo.get_order", new=AsyncMock(return_value=order)),
    patch("app.entities.marketplace_payments.service.repo.get_current_payment", new=AsyncMock(return_value=payment)),
    patch("app.entities.marketplace_payments.service._require_stripe", return_value=SimpleNamespace(STRIPE_SECRET_KEY="sk_test")),
  ):
    service.stripe = Mock()
    service.stripe.Refund.create.return_value = refund

    result = await service.request_order_refund(
      session,
      organization_id="org-1",
      order_id="order-1",
      reason="requested_by_customer",
    )

  service.stripe.Refund.create.assert_called_once_with(
    payment_intent="pi_123",
    reason="requested_by_customer",
    metadata={"organization_id": "org-1", "order_id": "order-1", "payment_id": "pay-1"},
  )
  assert result.status == "refund_pending"
  assert payment.status == "refund_pending"
  assert payment.stripe_refund_id == "re_123"
  assert order.financial_status == "refund_pending"


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
