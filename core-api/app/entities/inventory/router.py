from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.api.pagination import PaginatedResponse, PaginationParams, pagination_params
from shared.db.session import get_db_session
from shared.security.jwt import TokenClaims
from shared.security.permissions import require_permission

from . import service
from .schemas import (
  InventoryItemCreate,
  InventoryItemOut,
  InventoryItemUpdate,
  InventoryMovementCreate,
  InventoryMovementCreateResult,
  InventoryMovementOut,
)


router = APIRouter(prefix="/inventory", tags=["inventory"])

RequireEstoque = Depends(require_permission("estoque"))


@router.get("/items", response_model=PaginatedResponse[InventoryItemOut])
async def list_inventory_items(
  claims: TokenClaims = RequireEstoque,
  session: AsyncSession = Depends(get_db_session),
  pagination: PaginationParams = Depends(pagination_params),
  category: str | None = None,
  q: str | None = None,
  low_stock_only: bool = False,
  sort: str = Query(default="updated_at", pattern="^(updated_at|name|current_stock)$"),
):
  return await service.list_items(
    session,
    organization_id=claims.org,
    pagination=pagination,
    category=category,
    q=q,
    low_stock_only=low_stock_only,
    sort=sort,
  )


@router.post("/items", response_model=InventoryItemOut, status_code=status.HTTP_201_CREATED)
async def create_inventory_item(
  body: InventoryItemCreate,
  claims: TokenClaims = RequireEstoque,
  session: AsyncSession = Depends(get_db_session),
):
  result = await service.create_item(session, organization_id=claims.org, body=body)
  await session.commit()
  return result


@router.get("/items/{item_id}", response_model=InventoryItemOut)
async def get_inventory_item(
  item_id: str,
  claims: TokenClaims = RequireEstoque,
  session: AsyncSession = Depends(get_db_session),
):
  return await service.get_item(session, organization_id=claims.org, item_id=item_id)


@router.patch("/items/{item_id}", response_model=InventoryItemOut)
async def update_inventory_item(
  item_id: str,
  body: InventoryItemUpdate,
  claims: TokenClaims = RequireEstoque,
  session: AsyncSession = Depends(get_db_session),
):
  result = await service.update_item(
    session,
    organization_id=claims.org,
    item_id=item_id,
    body=body,
  )
  await session.commit()
  return result


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_inventory_item(
  item_id: str,
  claims: TokenClaims = RequireEstoque,
  session: AsyncSession = Depends(get_db_session),
):
  await service.delete_item(session, organization_id=claims.org, item_id=item_id)
  await session.commit()
  return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/items/{item_id}/movements", response_model=PaginatedResponse[InventoryMovementOut])
async def list_inventory_movements(
  item_id: str,
  claims: TokenClaims = RequireEstoque,
  session: AsyncSession = Depends(get_db_session),
  pagination: PaginationParams = Depends(pagination_params),
  movement_type: str | None = Query(default=None, pattern="^(entrada|saida)$"),
):
  return await service.list_item_movements(
    session,
    organization_id=claims.org,
    item_id=item_id,
    pagination=pagination,
    movement_type=movement_type,
  )


@router.post(
  "/items/{item_id}/movements", response_model=InventoryMovementCreateResult, status_code=status.HTTP_201_CREATED
)
async def create_inventory_movement(
  item_id: str,
  body: InventoryMovementCreate,
  claims: TokenClaims = RequireEstoque,
  session: AsyncSession = Depends(get_db_session),
):
  result = await service.create_movement(
    session,
    organization_id=claims.org,
    item_id=item_id,
    user_id=claims.sub,
    body=body,
  )
  await session.commit()
  return result
