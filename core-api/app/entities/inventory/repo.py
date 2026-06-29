from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.api.pagination import PaginationParams
from shared.db.models import InventoryItem, InventoryMovement


async def count_items(
  session: AsyncSession,
  *,
  organization_id: str,
  category: str | None = None,
  q: str | None = None,
  low_stock_only: bool = False,
) -> int:
  stmt = select(func.count()).select_from(InventoryItem).where(InventoryItem.organization_id == organization_id)
  if category is not None:
    stmt = stmt.where(InventoryItem.category == category)
  if q is not None:
    stmt = stmt.where(InventoryItem.name.ilike(f"%{q}%"))
  if low_stock_only:
    stmt = stmt.where(InventoryItem.current_stock < InventoryItem.min_stock)
  row = await session.execute(stmt)
  return int(row.scalar_one())


async def list_items(
  session: AsyncSession,
  *,
  organization_id: str,
  pagination: PaginationParams,
  category: str | None = None,
  q: str | None = None,
  low_stock_only: bool = False,
  sort: str = "updated_at",
) -> list[InventoryItem]:
  sort_col = InventoryItem.updated_at.desc()
  if sort == "name":
    sort_col = InventoryItem.name.asc()
  elif sort == "current_stock":
    sort_col = InventoryItem.current_stock.asc()
  stmt = (
    select(InventoryItem)
    .where(InventoryItem.organization_id == organization_id)
    .order_by(sort_col)
    .offset(pagination.offset)
    .limit(pagination.limit)
  )
  if category is not None:
    stmt = stmt.where(InventoryItem.category == category)
  if q is not None:
    stmt = stmt.where(InventoryItem.name.ilike(f"%{q}%"))
  if low_stock_only:
    stmt = stmt.where(InventoryItem.current_stock < InventoryItem.min_stock)
  row = await session.execute(stmt)
  return list(row.scalars().all())


async def get_item(session: AsyncSession, *, item_id: str) -> InventoryItem | None:
  row = await session.execute(select(InventoryItem).where(InventoryItem.id == item_id))
  return row.scalar_one_or_none()


async def create_item(session: AsyncSession, row: InventoryItem) -> InventoryItem:
  session.add(row)
  await session.flush()
  return row


async def count_item_movements(
  session: AsyncSession,
  *,
  organization_id: str,
  item_id: str,
  movement_type: str | None = None,
) -> int:
  stmt = (
    select(func.count())
    .select_from(InventoryMovement)
    .where(
      InventoryMovement.organization_id == organization_id,
      InventoryMovement.item_id == item_id,
    )
  )
  if movement_type is not None:
    stmt = stmt.where(InventoryMovement.movement_type == movement_type)
  row = await session.execute(stmt)
  return int(row.scalar_one())


async def list_item_movements(
  session: AsyncSession,
  *,
  organization_id: str,
  item_id: str,
  pagination: PaginationParams,
  movement_type: str | None = None,
) -> list[InventoryMovement]:
  stmt = (
    select(InventoryMovement)
    .where(
      InventoryMovement.organization_id == organization_id,
      InventoryMovement.item_id == item_id,
    )
    .order_by(InventoryMovement.created_at.desc())
    .offset(pagination.offset)
    .limit(pagination.limit)
  )
  if movement_type is not None:
    stmt = stmt.where(InventoryMovement.movement_type == movement_type)
  row = await session.execute(stmt)
  return list(row.scalars().all())


async def create_movement(session: AsyncSession, row: InventoryMovement) -> InventoryMovement:
  session.add(row)
  await session.flush()
  return row
