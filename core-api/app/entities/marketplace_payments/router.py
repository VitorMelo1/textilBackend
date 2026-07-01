from __future__ import annotations

from fastapi import APIRouter, Depends
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
