from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.session import get_db_session
from shared.security.permissions import require_permission

from . import service
from .schemas import (
  AccountOnboardingLinkRequest,
  AccountOnboardingLinkResponse,
  ConnectedAccountOut,
  MarketplaceFinanceSummary,
  OrderCheckoutSessionRequest,
  OrderCheckoutSessionResponse,
  OrderPaymentOut,
  OrderReceiptOut,
  OrderRefundRequest,
)

router = APIRouter(tags=["marketplace-payments"])


@router.get("/marketplace/connected-account", response_model=ConnectedAccountOut)
async def get_connected_account(
  claims=Depends(require_permission("financeiro")),
  session: AsyncSession = Depends(get_db_session),
):
  return await service.get_connected_account_status(session, organization_id=claims.org)


@router.post("/marketplace/connected-account", response_model=ConnectedAccountOut)
async def create_connected_account(
  claims=Depends(require_permission("financeiro")),
  session: AsyncSession = Depends(get_db_session),
):
  account = await service.ensure_connected_account(session, organization_id=claims.org)
  await session.commit()
  return account


@router.post("/marketplace/connected-account/onboarding-link", response_model=AccountOnboardingLinkResponse)
async def create_connected_account_onboarding_link(
  body: AccountOnboardingLinkRequest,
  claims=Depends(require_permission("financeiro")),
  session: AsyncSession = Depends(get_db_session),
):
  url = await service.create_onboarding_link(
    session,
    organization_id=claims.org,
    return_url=body.return_url,
    refresh_url=body.refresh_url,
  )
  await session.commit()
  return AccountOnboardingLinkResponse(onboarding_url=url)


@router.post("/marketplace/connected-account/sync", response_model=ConnectedAccountOut)
async def sync_connected_account(
  claims=Depends(require_permission("financeiro")),
  session: AsyncSession = Depends(get_db_session),
):
  account = await service.sync_connected_account_for_org(session, organization_id=claims.org)
  await session.commit()
  return account


@router.get("/marketplace/mercado-pago/oauth/callback")
async def mercado_pago_oauth_callback(
  code: str = Query(...),
  state: str = Query(...),
  session: AsyncSession = Depends(get_db_session),
):
  redirect_url = await service.handle_mercado_pago_oauth_callback(session, code=code, state=state)
  await session.commit()
  return RedirectResponse(redirect_url)


@router.post("/marketplace/mercado-pago/webhook")
async def mercado_pago_webhook(
  request: Request,
  payment_id: str | None = Query(None),
  session: AsyncSession = Depends(get_db_session),
):
  try:
    payload = await request.json()
  except Exception:
    payload = {}
  data = payload.get("data") if isinstance(payload, dict) else None
  mercado_pago_payment_id = None
  if isinstance(data, dict):
    mercado_pago_payment_id = data.get("id")
  if mercado_pago_payment_id is None and isinstance(payload, dict):
    mercado_pago_payment_id = payload.get("id") or payload.get("resource")
  if mercado_pago_payment_id is None:
    mercado_pago_payment_id = request.query_params.get("id")
  if isinstance(mercado_pago_payment_id, str) and "/" in mercado_pago_payment_id:
    mercado_pago_payment_id = mercado_pago_payment_id.rstrip("/").split("/")[-1]
  await service.process_mercado_pago_webhook(
    session,
    payment_id=payment_id,
    mercado_pago_payment_id=str(mercado_pago_payment_id) if mercado_pago_payment_id else None,
  )
  await session.commit()
  return {"received": True}


@router.get("/marketplace/finance/summary", response_model=MarketplaceFinanceSummary)
async def get_marketplace_finance_summary(
  claims=Depends(require_permission("financeiro")),
  session: AsyncSession = Depends(get_db_session),
):
  return await service.get_finance_summary(session, organization_id=claims.org)


@router.post("/orders/{order_id}/payments/checkout-session", response_model=OrderCheckoutSessionResponse)
async def create_order_checkout_session(
  order_id: str,
  body: OrderCheckoutSessionRequest,
  claims=Depends(require_permission("pedidos")),
  session: AsyncSession = Depends(get_db_session),
):
  checkout = await service.create_order_checkout_session(
    session,
    organization_id=claims.org,
    order_id=order_id,
    success_url=body.success_url,
    cancel_url=body.cancel_url,
  )
  await session.commit()
  return checkout


@router.get("/orders/{order_id}/payments/current", response_model=OrderPaymentOut)
async def get_current_order_payment(
  order_id: str,
  claims=Depends(require_permission("pedidos")),
  session: AsyncSession = Depends(get_db_session),
):
  return await service.get_current_order_payment(session, organization_id=claims.org, order_id=order_id)


@router.post("/orders/{order_id}/payments/refund", response_model=OrderPaymentOut)
async def refund_order_payment(
  order_id: str,
  body: OrderRefundRequest,
  claims=Depends(require_permission("financeiro")),
  session: AsyncSession = Depends(get_db_session),
):
  payment = await service.request_order_refund(
    session,
    organization_id=claims.org,
    order_id=order_id,
    reason=body.reason,
  )
  await session.commit()
  return payment


@router.get("/orders/{order_id}/receipt", response_model=OrderReceiptOut)
async def get_order_receipt(
  order_id: str,
  claims=Depends(require_permission("pedidos")),
  session: AsyncSession = Depends(get_db_session),
):
  return await service.get_order_receipt(session, organization_id=claims.org, order_id=order_id)
