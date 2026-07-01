from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import Order, OrderPayment, StripeConnectedAccount


async def get_connected_account(
  session: AsyncSession,
  *,
  organization_id: str,
) -> StripeConnectedAccount | None:
  q = await session.execute(
    select(StripeConnectedAccount).where(StripeConnectedAccount.organization_id == organization_id)
  )
  return q.scalar_one_or_none()


async def get_connected_account_by_stripe_id(
  session: AsyncSession,
  *,
  stripe_account_id: str,
) -> StripeConnectedAccount | None:
  q = await session.execute(
    select(StripeConnectedAccount).where(StripeConnectedAccount.stripe_account_id == stripe_account_id)
  )
  return q.scalar_one_or_none()


async def create_connected_account(
  session: AsyncSession,
  row: StripeConnectedAccount,
) -> StripeConnectedAccount:
  session.add(row)
  await session.flush()
  return row


async def get_order(session: AsyncSession, *, order_id: str) -> Order | None:
  q = await session.execute(select(Order).where(Order.id == order_id))
  return q.scalar_one_or_none()


async def create_order_payment(session: AsyncSession, row: OrderPayment) -> OrderPayment:
  session.add(row)
  await session.flush()
  return row


async def get_current_payment(
  session: AsyncSession,
  *,
  order_id: str,
) -> OrderPayment | None:
  q = await session.execute(
    select(OrderPayment)
    .where(OrderPayment.order_id == order_id)
    .order_by(OrderPayment.created_at.desc())
    .limit(1)
  )
  return q.scalar_one_or_none()


async def get_payment_by_checkout_session(
  session: AsyncSession,
  *,
  checkout_session_id: str,
) -> OrderPayment | None:
  q = await session.execute(
    select(OrderPayment).where(OrderPayment.stripe_checkout_session_id == checkout_session_id)
  )
  return q.scalar_one_or_none()


async def get_payment_by_payment_intent(
  session: AsyncSession,
  *,
  payment_intent_id: str,
) -> OrderPayment | None:
  q = await session.execute(
    select(OrderPayment).where(OrderPayment.stripe_payment_intent_id == payment_intent_id)
  )
  return q.scalar_one_or_none()


async def list_payments_for_org(
  session: AsyncSession,
  *,
  organization_id: str,
  limit: int = 100,
) -> list[tuple[OrderPayment, Order]]:
  q = await session.execute(
    select(OrderPayment, Order)
    .join(Order, Order.id == OrderPayment.order_id)
    .where(OrderPayment.organization_id == organization_id)
    .order_by(OrderPayment.created_at.desc())
    .limit(limit)
  )
  return [(payment, order) for payment, order in q.all()]
