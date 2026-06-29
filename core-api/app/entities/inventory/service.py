from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.api.pagination import PaginatedResponse, PaginationParams
from shared.db.models import InventoryItem, InventoryMovement

from . import repo
from .schemas import (
  InventoryItemCreate,
  InventoryItemOut,
  InventoryItemUpdate,
  InventoryMovementCreate,
  InventoryMovementOut,
)


def item_to_out(row: InventoryItem) -> InventoryItemOut:
  return InventoryItemOut(
    id=row.id,
    organization_id=row.organization_id,
    name=row.name,
    category=row.category,
    current_stock=float(row.current_stock),
    min_stock=float(row.min_stock),
    unit=row.unit,
    unit_cost=float(row.unit_cost),
    supplier=row.supplier,
    is_below_min=float(row.current_stock) < float(row.min_stock),
    created_at=row.created_at,
    updated_at=row.updated_at,
  )


def movement_to_out(row: InventoryMovement) -> InventoryMovementOut:
  return InventoryMovementOut(
    id=row.id,
    organization_id=row.organization_id,
    item_id=row.item_id,
    movement_type=row.movement_type,
    quantity=float(row.quantity),
    reason=row.reason,
    recorded_by_user_id=row.recorded_by_user_id,
    created_at=row.created_at,
  )


async def list_items(
  session: AsyncSession,
  *,
  organization_id: str,
  pagination: PaginationParams,
  category: str | None = None,
  q: str | None = None,
  low_stock_only: bool = False,
  sort: str = "updated_at",
) -> PaginatedResponse[InventoryItemOut]:
  total = await repo.count_items(
    session,
    organization_id=organization_id,
    category=category,
    q=q,
    low_stock_only=low_stock_only,
  )
  rows = await repo.list_items(
    session,
    organization_id=organization_id,
    pagination=pagination,
    category=category,
    q=q,
    low_stock_only=low_stock_only,
    sort=sort,
  )
  return PaginatedResponse(
    items=[item_to_out(r) for r in rows],
    total=total,
    page=pagination.page,
    page_size=pagination.page_size,
  )


async def create_item(
  session: AsyncSession,
  *,
  organization_id: str,
  body: InventoryItemCreate,
) -> InventoryItemOut:
  row = InventoryItem(
    organization_id=organization_id,
    name=body.name,
    category=body.category,
    current_stock=body.current_stock,
    min_stock=body.min_stock,
    unit=body.unit,
    unit_cost=body.unit_cost,
    supplier=body.supplier,
  )
  row = await repo.create_item(session, row)
  return item_to_out(row)


async def get_item(
  session: AsyncSession,
  *,
  organization_id: str,
  item_id: str,
) -> InventoryItemOut:
  row = await repo.get_item(session, item_id=item_id)
  if row is None or row.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="inventory item not found")
  return item_to_out(row)


async def update_item(
  session: AsyncSession,
  *,
  organization_id: str,
  item_id: str,
  body: InventoryItemUpdate,
) -> InventoryItemOut:
  row = await repo.get_item(session, item_id=item_id)
  if row is None or row.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="inventory item not found")
  for field in ("name", "category", "min_stock", "unit", "unit_cost", "supplier"):
    value = getattr(body, field)
    if value is not None:
      setattr(row, field, value)
  await session.flush()
  return item_to_out(row)


async def delete_item(
  session: AsyncSession,
  *,
  organization_id: str,
  item_id: str,
) -> None:
  row = await repo.get_item(session, item_id=item_id)
  if row is None or row.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="inventory item not found")
  await session.delete(row)
  await session.flush()


async def list_item_movements(
  session: AsyncSession,
  *,
  organization_id: str,
  item_id: str,
  pagination: PaginationParams,
  movement_type: str | None = None,
) -> PaginatedResponse[InventoryMovementOut]:
  row = await repo.get_item(session, item_id=item_id)
  if row is None or row.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="inventory item not found")
  total = await repo.count_item_movements(
    session,
    organization_id=organization_id,
    item_id=item_id,
    movement_type=movement_type,
  )
  rows = await repo.list_item_movements(
    session,
    organization_id=organization_id,
    item_id=item_id,
    pagination=pagination,
    movement_type=movement_type,
  )
  return PaginatedResponse(
    items=[movement_to_out(r) for r in rows],
    total=total,
    page=pagination.page,
    page_size=pagination.page_size,
  )


async def create_movement(
  session: AsyncSession,
  *,
  organization_id: str,
  item_id: str,
  user_id: str,
  body: InventoryMovementCreate,
) -> dict[str, object]:
  item = await repo.get_item(session, item_id=item_id)
  if item is None or item.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="inventory item not found")

  current_stock = float(item.current_stock)
  quantity = float(body.quantity)
  if body.movement_type == "saida" and current_stock - quantity < 0:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="insufficient stock")

  if body.movement_type == "entrada":
    item.current_stock = current_stock + quantity
  else:
    item.current_stock = current_stock - quantity

  movement = InventoryMovement(
    organization_id=organization_id,
    item_id=item_id,
    movement_type=body.movement_type,
    quantity=quantity,
    reason=body.reason,
    recorded_by_user_id=user_id,
  )
  movement = await repo.create_movement(session, movement)
  await session.flush()
  return {
    "movement": movement_to_out(movement),
    "current_stock_after": float(item.current_stock),
  }
