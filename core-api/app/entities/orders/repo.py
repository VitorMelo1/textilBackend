from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.api.pagination import PaginationParams
from shared.db.models import Order, OrderBatch, TechnicalSheet


async def count_orders(
  session: AsyncSession,
  *,
  organization_id: str,
  stage: str | None = None,
  priority: str | None = None,
  client_name: str | None = None,
  product_name: str | None = None,
  deadline_from: date | None = None,
  deadline_to: date | None = None,
) -> int:
  stmt = select(func.count()).select_from(Order).where(Order.organization_id == organization_id)
  if stage is not None:
    stmt = stmt.where(Order.stage == stage)
  if priority is not None:
    stmt = stmt.where(Order.priority == priority)
  if client_name is not None:
    stmt = stmt.where(Order.client_name.ilike(f"%{client_name}%"))
  if product_name is not None:
    stmt = stmt.where(Order.product_name.ilike(f"%{product_name}%"))
  if deadline_from is not None:
    stmt = stmt.where(Order.deadline >= deadline_from)
  if deadline_to is not None:
    stmt = stmt.where(Order.deadline <= deadline_to)
  q = await session.execute(stmt)
  return int(q.scalar_one())


async def list_orders(
  session: AsyncSession,
  *,
  organization_id: str,
  pagination: PaginationParams,
  stage: str | None = None,
  priority: str | None = None,
  client_name: str | None = None,
  product_name: str | None = None,
  deadline_from: date | None = None,
  deadline_to: date | None = None,
  sort: str = "created_at",
  order: str = "desc",
) -> list[Order]:
  sort_col = Order.created_at
  if sort == "deadline":
    sort_col = Order.deadline
  elif sort == "order_code":
    sort_col = Order.order_code
  if order.lower() == "asc":
    sort_col = sort_col.asc()
  else:
    sort_col = sort_col.desc()

  stmt = (
    select(Order)
    .where(Order.organization_id == organization_id)
    .order_by(sort_col)
    .offset(pagination.offset)
    .limit(pagination.limit)
  )
  if stage is not None:
    stmt = stmt.where(Order.stage == stage)
  if priority is not None:
    stmt = stmt.where(Order.priority == priority)
  if client_name is not None:
    stmt = stmt.where(Order.client_name.ilike(f"%{client_name}%"))
  if product_name is not None:
    stmt = stmt.where(Order.product_name.ilike(f"%{product_name}%"))
  if deadline_from is not None:
    stmt = stmt.where(Order.deadline >= deadline_from)
  if deadline_to is not None:
    stmt = stmt.where(Order.deadline <= deadline_to)
  q = await session.execute(stmt)
  return list(q.scalars().all())


async def get_order_by_id(session: AsyncSession, *, order_id: str) -> Order | None:
  q = await session.execute(select(Order).where(Order.id == order_id))
  return q.scalar_one_or_none()


async def get_order_by_code(
  session: AsyncSession,
  *,
  organization_id: str,
  order_code: str,
) -> Order | None:
  q = await session.execute(
    select(Order).where(Order.organization_id == organization_id, Order.order_code == order_code)
  )
  return q.scalar_one_or_none()


async def create_order(session: AsyncSession, row: Order) -> Order:
  session.add(row)
  await session.flush()
  return row


async def get_sheet(session: AsyncSession, *, organization_id: str, sheet_id: str) -> TechnicalSheet | None:
  q = await session.execute(
    select(TechnicalSheet).where(
      TechnicalSheet.id == sheet_id,
      TechnicalSheet.organization_id == organization_id,
    )
  )
  return q.scalar_one_or_none()


async def get_batch_by_id(session: AsyncSession, *, batch_id: str) -> OrderBatch | None:
  q = await session.execute(select(OrderBatch).where(OrderBatch.id == batch_id))
  return q.scalar_one_or_none()


async def get_batch_by_lot(
  session: AsyncSession,
  *,
  order_id: str,
  lot_number: str,
) -> OrderBatch | None:
  q = await session.execute(
    select(OrderBatch).where(OrderBatch.order_id == order_id, OrderBatch.lot_number == lot_number)
  )
  return q.scalar_one_or_none()


async def create_batch(session: AsyncSession, row: OrderBatch) -> OrderBatch:
  session.add(row)
  await session.flush()
  return row
