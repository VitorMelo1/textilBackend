from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.api.pagination import PaginatedResponse, PaginationParams
from shared.db.models import CostCalculation, CostCalculationLabor, CostCalculationMaterial

from . import repo
from .schemas import (
  CostCalculationCreate,
  CostCalculationLaborCreate,
  CostCalculationLaborOut,
  CostCalculationLaborUpdate,
  CostCalculationMaterialCreate,
  CostCalculationMaterialOut,
  CostCalculationMaterialUpdate,
  CostCalculationOut,
  CostCalculationUpdate,
)


def calc_material_total(quantity: float, unit_cost: float) -> float:
  return float(quantity) * float(unit_cost)


def calc_labor_total(hours: float, hourly_rate: float) -> float:
  return float(hours) * float(hourly_rate)


def calc_suggested_price(cost_per_unit: float, profit_margin: float) -> float:
  return float(cost_per_unit) * (1 + (float(profit_margin) / 100.0))


def to_out(row: CostCalculation) -> CostCalculationOut:
  return CostCalculationOut(
    id=row.id,
    organization_id=row.organization_id,
    product_name=row.product_name,
    quantity=row.quantity,
    total_material_cost=float(row.total_material_cost),
    total_labor_cost=float(row.total_labor_cost),
    total_cost=float(row.total_cost),
    cost_per_unit=float(row.cost_per_unit),
    profit_margin=float(row.profit_margin),
    suggested_price=float(row.suggested_price),
    created_at=row.created_at,
    updated_at=row.updated_at,
  )


def material_to_out(row: CostCalculationMaterial) -> CostCalculationMaterialOut:
  return CostCalculationMaterialOut(
    id=row.id,
    organization_id=row.organization_id,
    calculation_id=row.calculation_id,
    name=row.name,
    quantity=float(row.quantity),
    unit=row.unit,
    unit_cost=float(row.unit_cost),
    total_cost=float(row.total_cost),
    sort_order=row.sort_order,
    created_at=row.created_at,
    updated_at=row.updated_at,
  )


def labor_to_out(row: CostCalculationLabor) -> CostCalculationLaborOut:
  return CostCalculationLaborOut(
    id=row.id,
    organization_id=row.organization_id,
    calculation_id=row.calculation_id,
    description=row.description,
    hours=float(row.hours),
    hourly_rate=float(row.hourly_rate),
    total_cost=float(row.total_cost),
    sort_order=row.sort_order,
    created_at=row.created_at,
    updated_at=row.updated_at,
  )


async def recalculate_totals(session: AsyncSession, row: CostCalculation) -> None:
  materials = await repo.list_materials(session, calculation_id=row.id)
  labor = await repo.list_labor(session, calculation_id=row.id)
  total_material_cost = sum(float(m.total_cost) for m in materials)
  total_labor_cost = sum(float(labor_line.total_cost) for labor_line in labor)
  total_cost = total_material_cost + total_labor_cost
  cost_per_unit = total_cost / float(row.quantity) if row.quantity > 0 else 0.0
  row.total_material_cost = total_material_cost
  row.total_labor_cost = total_labor_cost
  row.total_cost = total_cost
  row.cost_per_unit = cost_per_unit
  row.suggested_price = calc_suggested_price(cost_per_unit, float(row.profit_margin))
  await session.flush()


async def list_for_org(
  session: AsyncSession,
  *,
  organization_id: str,
  pagination: PaginationParams,
  q: str | None = None,
) -> PaginatedResponse[CostCalculationOut]:
  total = await repo.count_calculations(session, organization_id=organization_id, q=q)
  rows = await repo.list_calculations(
    session,
    organization_id=organization_id,
    pagination=pagination,
    q=q,
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
  body: CostCalculationCreate,
) -> CostCalculationOut:
  row = CostCalculation(
    organization_id=organization_id,
    product_name=body.product_name,
    quantity=body.quantity,
    profit_margin=body.profit_margin,
    total_material_cost=0,
    total_labor_cost=0,
    total_cost=0,
    cost_per_unit=0,
    suggested_price=0,
  )
  row = await repo.create_calculation(session, row)
  await recalculate_totals(session, row)
  return to_out(row)


async def get_by_id(
  session: AsyncSession,
  *,
  organization_id: str,
  calculation_id: str,
) -> CostCalculationOut:
  row = await repo.get_calculation(session, calculation_id=calculation_id)
  if row is None or row.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="cost calculation not found")
  return to_out(row)


async def update(
  session: AsyncSession,
  *,
  organization_id: str,
  calculation_id: str,
  body: CostCalculationUpdate,
) -> CostCalculationOut:
  row = await repo.get_calculation(session, calculation_id=calculation_id)
  if row is None or row.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="cost calculation not found")
  for field in ("product_name", "quantity", "profit_margin"):
    value = getattr(body, field)
    if value is not None:
      setattr(row, field, value)
  await recalculate_totals(session, row)
  return to_out(row)


async def delete(
  session: AsyncSession,
  *,
  organization_id: str,
  calculation_id: str,
) -> None:
  row = await repo.get_calculation(session, calculation_id=calculation_id)
  if row is None or row.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="cost calculation not found")
  await session.delete(row)
  await session.flush()


async def ensure_calculation_for_org(
  session: AsyncSession,
  *,
  organization_id: str,
  calculation_id: str,
) -> CostCalculation:
  row = await repo.get_calculation(session, calculation_id=calculation_id)
  if row is None or row.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="cost calculation not found")
  return row


async def create_material(
  session: AsyncSession,
  *,
  organization_id: str,
  calculation_id: str,
  body: CostCalculationMaterialCreate,
) -> CostCalculationMaterialOut:
  calc = await ensure_calculation_for_org(
    session,
    organization_id=organization_id,
    calculation_id=calculation_id,
  )
  row = CostCalculationMaterial(
    organization_id=organization_id,
    calculation_id=calculation_id,
    name=body.name,
    quantity=body.quantity,
    unit=body.unit,
    unit_cost=body.unit_cost,
    total_cost=calc_material_total(body.quantity, body.unit_cost),
    sort_order=body.sort_order,
  )
  row = await repo.create_material(session, row)
  await recalculate_totals(session, calc)
  return material_to_out(row)


async def update_material(
  session: AsyncSession,
  *,
  organization_id: str,
  material_id: str,
  body: CostCalculationMaterialUpdate,
) -> CostCalculationMaterialOut:
  row = await repo.get_material(session, material_id=material_id)
  if row is None or row.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="cost material not found")
  if body.name is not None:
    row.name = body.name
  if body.quantity is not None:
    row.quantity = body.quantity
  if body.unit is not None:
    row.unit = body.unit
  if body.unit_cost is not None:
    row.unit_cost = body.unit_cost
  if body.sort_order is not None:
    row.sort_order = body.sort_order
  row.total_cost = calc_material_total(float(row.quantity), float(row.unit_cost))
  calc = await ensure_calculation_for_org(
    session,
    organization_id=organization_id,
    calculation_id=row.calculation_id,
  )
  await recalculate_totals(session, calc)
  return material_to_out(row)


async def delete_material(
  session: AsyncSession,
  *,
  organization_id: str,
  material_id: str,
) -> None:
  row = await repo.get_material(session, material_id=material_id)
  if row is None or row.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="cost material not found")
  calc = await ensure_calculation_for_org(
    session,
    organization_id=organization_id,
    calculation_id=row.calculation_id,
  )
  await session.delete(row)
  await session.flush()
  await recalculate_totals(session, calc)


async def create_labor(
  session: AsyncSession,
  *,
  organization_id: str,
  calculation_id: str,
  body: CostCalculationLaborCreate,
) -> CostCalculationLaborOut:
  calc = await ensure_calculation_for_org(
    session,
    organization_id=organization_id,
    calculation_id=calculation_id,
  )
  row = CostCalculationLabor(
    organization_id=organization_id,
    calculation_id=calculation_id,
    description=body.description,
    hours=body.hours,
    hourly_rate=body.hourly_rate,
    total_cost=calc_labor_total(body.hours, body.hourly_rate),
    sort_order=body.sort_order,
  )
  row = await repo.create_labor(session, row)
  await recalculate_totals(session, calc)
  return labor_to_out(row)


async def update_labor(
  session: AsyncSession,
  *,
  organization_id: str,
  labor_id: str,
  body: CostCalculationLaborUpdate,
) -> CostCalculationLaborOut:
  row = await repo.get_labor(session, labor_id=labor_id)
  if row is None or row.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="cost labor not found")
  if body.description is not None:
    row.description = body.description
  if body.hours is not None:
    row.hours = body.hours
  if body.hourly_rate is not None:
    row.hourly_rate = body.hourly_rate
  if body.sort_order is not None:
    row.sort_order = body.sort_order
  row.total_cost = calc_labor_total(float(row.hours), float(row.hourly_rate))
  calc = await ensure_calculation_for_org(
    session,
    organization_id=organization_id,
    calculation_id=row.calculation_id,
  )
  await recalculate_totals(session, calc)
  return labor_to_out(row)


async def delete_labor(
  session: AsyncSession,
  *,
  organization_id: str,
  labor_id: str,
) -> None:
  row = await repo.get_labor(session, labor_id=labor_id)
  if row is None or row.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="cost labor not found")
  calc = await ensure_calculation_for_org(
    session,
    organization_id=organization_id,
    calculation_id=row.calculation_id,
  )
  await session.delete(row)
  await session.flush()
  await recalculate_totals(session, calc)
