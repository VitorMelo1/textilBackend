from __future__ import annotations

from datetime import date
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.api.pagination import PaginatedResponse, PaginationParams
from shared.db.models import Order, OrderBatch

from . import repo
from .schemas import OrderBatchCreate, OrderBatchOut, OrderBatchUpdate, OrderCreate, OrderOut, OrderUpdate


def compute_days_until_deadline(deadline: date) -> int:
  return (deadline - date.today()).days


def generate_order_code(today: date | None = None) -> str:
  """Código de negócio gerado no servidor (data + sufixo aleatório, sem corrida de contador)."""
  stamp = (today or date.today()).strftime("%Y%m%d")
  return f"PED-{stamp}-{uuid4().hex[:4].upper()}"


def to_out(row: Order) -> OrderOut:
  return OrderOut(
    id=row.id,
    organization_id=row.organization_id,
    order_code=row.order_code,
    client_name=row.client_name,
    product_name=row.product_name,
    quantity=row.quantity,
    deadline=row.deadline,
    days_until_deadline=compute_days_until_deadline(row.deadline),
    priority=row.priority,
    notes=row.notes,
    stage=row.stage,
    progress=row.progress,
    unit_price=float(row.unit_price) if row.unit_price is not None else 0.0,
    technical_sheet_id=row.technical_sheet_id,
    created_at=row.created_at,
    updated_at=row.updated_at,
  )


async def list_for_org(
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
) -> PaginatedResponse[OrderOut]:
  total = await repo.count_orders(
    session,
    organization_id=organization_id,
    stage=stage,
    priority=priority,
    client_name=client_name,
    product_name=product_name,
    deadline_from=deadline_from,
    deadline_to=deadline_to,
  )
  rows = await repo.list_orders(
    session,
    organization_id=organization_id,
    pagination=pagination,
    stage=stage,
    priority=priority,
    client_name=client_name,
    product_name=product_name,
    deadline_from=deadline_from,
    deadline_to=deadline_to,
    sort=sort,
    order=order,
  )
  return PaginatedResponse(
    items=[to_out(r) for r in rows],
    total=total,
    page=pagination.page,
    page_size=pagination.page_size,
  )


async def create(
  session: AsyncSession,
  *,
  organization_id: str,
  body: OrderCreate,
) -> OrderOut:
  order_code = body.order_code or generate_order_code()
  existing = await repo.get_order_by_code(
    session,
    organization_id=organization_id,
    order_code=order_code,
  )
  if existing is not None:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="order_code already exists")
  if body.technical_sheet_id is not None:
    sheet = await repo.get_sheet(session, organization_id=organization_id, sheet_id=body.technical_sheet_id)
    if sheet is None:
      raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="technical sheet not found")
  row = Order(
    organization_id=organization_id,
    order_code=order_code,
    client_name=body.client_name,
    product_name=body.product_name,
    quantity=body.quantity,
    deadline=body.deadline,
    priority=body.priority,
    notes=body.notes,
    stage=body.stage,
    progress=body.progress,
    unit_price=body.unit_price,
    technical_sheet_id=body.technical_sheet_id,
  )
  row = await repo.create_order(session, row)
  return to_out(row)


async def get_by_id(
  session: AsyncSession,
  *,
  organization_id: str,
  order_id: str,
) -> OrderOut:
  row = await repo.get_order_by_id(session, order_id=order_id)
  if row is None or row.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="order not found")
  return to_out(row)


async def update(
  session: AsyncSession,
  *,
  organization_id: str,
  order_id: str,
  body: OrderUpdate,
) -> OrderOut:
  row = await repo.get_order_by_id(session, order_id=order_id)
  if row is None or row.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="order not found")

  if body.technical_sheet_id is not None:
    sheet = await repo.get_sheet(session, organization_id=organization_id, sheet_id=body.technical_sheet_id)
    if sheet is None:
      raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="technical sheet not found")

  for field in (
    "client_name",
    "product_name",
    "quantity",
    "deadline",
    "priority",
    "notes",
    "stage",
    "progress",
    "unit_price",
    "technical_sheet_id",
  ):
    value = getattr(body, field)
    if value is not None:
      setattr(row, field, value)
  await session.flush()
  await session.refresh(row)
  return to_out(row)


async def delete(
  session: AsyncSession,
  *,
  organization_id: str,
  order_id: str,
) -> None:
  row = await repo.get_order_by_id(session, order_id=order_id)
  if row is None or row.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="order not found")
  await session.delete(row)
  await session.flush()


def batch_to_out(row: OrderBatch) -> OrderBatchOut:
  return OrderBatchOut(
    id=row.id,
    organization_id=row.organization_id,
    order_id=row.order_id,
    lot_number=row.lot_number,
    quantity_sent=row.quantity_sent,
    quantity_completed=row.quantity_completed,
    status=row.status,
    sent_date=row.sent_date,
    completed_date=row.completed_date,
    created_at=row.created_at,
    updated_at=row.updated_at,
  )


async def create_batch(
  session: AsyncSession,
  *,
  organization_id: str,
  order_id: str,
  body: OrderBatchCreate,
) -> OrderBatchOut:
  order = await repo.get_order_by_id(session, order_id=order_id)
  if order is None or order.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="order not found")
  existing = await repo.get_batch_by_lot(session, order_id=order_id, lot_number=body.lot_number)
  if existing is not None:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="lot_number already exists")
  row = OrderBatch(
    organization_id=organization_id,
    order_id=order_id,
    lot_number=body.lot_number,
    quantity_sent=body.quantity_sent,
    quantity_completed=body.quantity_completed,
    status=body.status,
    sent_date=body.sent_date,
    completed_date=body.completed_date,
  )
  row = await repo.create_batch(session, row)
  return batch_to_out(row)


async def update_batch(
  session: AsyncSession,
  *,
  organization_id: str,
  batch_id: str,
  body: OrderBatchUpdate,
) -> OrderBatchOut:
  row = await repo.get_batch_by_id(session, batch_id=batch_id)
  if row is None or row.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="batch not found")
  if body.lot_number is not None and body.lot_number != row.lot_number:
    existing = await repo.get_batch_by_lot(session, order_id=row.order_id, lot_number=body.lot_number)
    if existing is not None:
      raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="lot_number already exists")

  for field in (
    "lot_number",
    "quantity_sent",
    "quantity_completed",
    "status",
    "sent_date",
    "completed_date",
  ):
    value = getattr(body, field)
    if value is not None:
      setattr(row, field, value)
  await session.flush()
  return batch_to_out(row)


async def delete_batch(
  session: AsyncSession,
  *,
  organization_id: str,
  batch_id: str,
) -> None:
  row = await repo.get_batch_by_id(session, batch_id=batch_id)
  if row is None or row.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="batch not found")
  await session.delete(row)
  await session.flush()
