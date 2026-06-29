from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.api.pagination import PaginationParams
from shared.db.models import CostCalculation, CostCalculationLabor, CostCalculationMaterial


async def count_calculations(session: AsyncSession, *, organization_id: str, q: str | None = None) -> int:
  stmt = select(func.count()).select_from(CostCalculation).where(CostCalculation.organization_id == organization_id)
  if q is not None:
    stmt = stmt.where(CostCalculation.product_name.ilike(f"%{q}%"))
  row = await session.execute(stmt)
  return int(row.scalar_one())


async def list_calculations(
  session: AsyncSession,
  *,
  organization_id: str,
  pagination: PaginationParams,
  q: str | None = None,
) -> list[CostCalculation]:
  stmt = (
    select(CostCalculation)
    .where(CostCalculation.organization_id == organization_id)
    .order_by(CostCalculation.created_at.desc())
    .offset(pagination.offset)
    .limit(pagination.limit)
  )
  if q is not None:
    stmt = stmt.where(CostCalculation.product_name.ilike(f"%{q}%"))
  row = await session.execute(stmt)
  return list(row.scalars().all())


async def get_calculation(session: AsyncSession, *, calculation_id: str) -> CostCalculation | None:
  row = await session.execute(select(CostCalculation).where(CostCalculation.id == calculation_id))
  return row.scalar_one_or_none()


async def create_calculation(session: AsyncSession, row: CostCalculation) -> CostCalculation:
  session.add(row)
  await session.flush()
  return row


async def list_materials(session: AsyncSession, *, calculation_id: str) -> list[CostCalculationMaterial]:
  row = await session.execute(
    select(CostCalculationMaterial)
    .where(CostCalculationMaterial.calculation_id == calculation_id)
    .order_by(CostCalculationMaterial.sort_order.asc(), CostCalculationMaterial.created_at.asc())
  )
  return list(row.scalars().all())


async def list_labor(session: AsyncSession, *, calculation_id: str) -> list[CostCalculationLabor]:
  row = await session.execute(
    select(CostCalculationLabor)
    .where(CostCalculationLabor.calculation_id == calculation_id)
    .order_by(CostCalculationLabor.sort_order.asc(), CostCalculationLabor.created_at.asc())
  )
  return list(row.scalars().all())


async def get_material(session: AsyncSession, *, material_id: str) -> CostCalculationMaterial | None:
  row = await session.execute(select(CostCalculationMaterial).where(CostCalculationMaterial.id == material_id))
  return row.scalar_one_or_none()


async def get_labor(session: AsyncSession, *, labor_id: str) -> CostCalculationLabor | None:
  row = await session.execute(select(CostCalculationLabor).where(CostCalculationLabor.id == labor_id))
  return row.scalar_one_or_none()


async def create_material(session: AsyncSession, row: CostCalculationMaterial) -> CostCalculationMaterial:
  session.add(row)
  await session.flush()
  return row


async def create_labor(session: AsyncSession, row: CostCalculationLabor) -> CostCalculationLabor:
  session.add(row)
  await session.flush()
  return row
