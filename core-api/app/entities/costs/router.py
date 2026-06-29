from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.api.pagination import PaginatedResponse, PaginationParams, pagination_params
from shared.db.session import get_db_session
from shared.security.jwt import TokenClaims
from shared.security.permissions import require_permission

from . import service
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


router = APIRouter(prefix="/cost-calculations", tags=["costs"])
material_router = APIRouter(prefix="/cost-calculation-materials", tags=["costs"])
labor_router = APIRouter(prefix="/cost-calculation-labor", tags=["costs"])

RequireCustos = Depends(require_permission("custos"))


@router.get("", response_model=PaginatedResponse[CostCalculationOut])
async def list_cost_calculations(
  claims: TokenClaims = RequireCustos,
  session: AsyncSession = Depends(get_db_session),
  pagination: PaginationParams = Depends(pagination_params),
  q: str | None = None,
):
  return await service.list_for_org(
    session,
    organization_id=claims.org,
    pagination=pagination,
    q=q,
  )


@router.post("", response_model=CostCalculationOut, status_code=status.HTTP_201_CREATED)
async def create_cost_calculation(
  body: CostCalculationCreate,
  claims: TokenClaims = RequireCustos,
  session: AsyncSession = Depends(get_db_session),
):
  result = await service.create(session, organization_id=claims.org, body=body)
  await session.commit()
  return result


@router.get("/{calculation_id}", response_model=CostCalculationOut)
async def get_cost_calculation(
  calculation_id: str,
  claims: TokenClaims = RequireCustos,
  session: AsyncSession = Depends(get_db_session),
):
  return await service.get_by_id(
    session,
    organization_id=claims.org,
    calculation_id=calculation_id,
  )


@router.patch("/{calculation_id}", response_model=CostCalculationOut)
async def update_cost_calculation(
  calculation_id: str,
  body: CostCalculationUpdate,
  claims: TokenClaims = RequireCustos,
  session: AsyncSession = Depends(get_db_session),
):
  result = await service.update(
    session,
    organization_id=claims.org,
    calculation_id=calculation_id,
    body=body,
  )
  await session.commit()
  return result


@router.delete("/{calculation_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_cost_calculation(
  calculation_id: str,
  claims: TokenClaims = RequireCustos,
  session: AsyncSession = Depends(get_db_session),
):
  await service.delete(session, organization_id=claims.org, calculation_id=calculation_id)
  await session.commit()
  return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
  "/{calculation_id}/materials", response_model=CostCalculationMaterialOut, status_code=status.HTTP_201_CREATED
)
async def create_cost_material(
  calculation_id: str,
  body: CostCalculationMaterialCreate,
  claims: TokenClaims = RequireCustos,
  session: AsyncSession = Depends(get_db_session),
):
  result = await service.create_material(
    session,
    organization_id=claims.org,
    calculation_id=calculation_id,
    body=body,
  )
  await session.commit()
  return result


@material_router.patch("/{material_id}", response_model=CostCalculationMaterialOut)
async def update_cost_material(
  material_id: str,
  body: CostCalculationMaterialUpdate,
  claims: TokenClaims = RequireCustos,
  session: AsyncSession = Depends(get_db_session),
):
  result = await service.update_material(
    session,
    organization_id=claims.org,
    material_id=material_id,
    body=body,
  )
  await session.commit()
  return result


@material_router.delete("/{material_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_cost_material(
  material_id: str,
  claims: TokenClaims = RequireCustos,
  session: AsyncSession = Depends(get_db_session),
):
  await service.delete_material(session, organization_id=claims.org, material_id=material_id)
  await session.commit()
  return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{calculation_id}/labor", response_model=CostCalculationLaborOut, status_code=status.HTTP_201_CREATED)
async def create_cost_labor(
  calculation_id: str,
  body: CostCalculationLaborCreate,
  claims: TokenClaims = RequireCustos,
  session: AsyncSession = Depends(get_db_session),
):
  result = await service.create_labor(
    session,
    organization_id=claims.org,
    calculation_id=calculation_id,
    body=body,
  )
  await session.commit()
  return result


@labor_router.patch("/{labor_id}", response_model=CostCalculationLaborOut)
async def update_cost_labor(
  labor_id: str,
  body: CostCalculationLaborUpdate,
  claims: TokenClaims = RequireCustos,
  session: AsyncSession = Depends(get_db_session),
):
  result = await service.update_labor(
    session,
    organization_id=claims.org,
    labor_id=labor_id,
    body=body,
  )
  await session.commit()
  return result


@labor_router.delete("/{labor_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_cost_labor(
  labor_id: str,
  claims: TokenClaims = RequireCustos,
  session: AsyncSession = Depends(get_db_session),
):
  await service.delete_labor(session, organization_id=claims.org, labor_id=labor_id)
  await session.commit()
  return Response(status_code=status.HTTP_204_NO_CONTENT)
