from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.api.pagination import PaginatedResponse, PaginationParams, pagination_params
from shared.db.session import get_db_session
from shared.security.jwt import TokenClaims
from shared.security.permissions import require_permission

from . import service
from .schemas import OrderBatchCreate, OrderBatchOut, OrderBatchUpdate, OrderCreate, OrderOut, OrderUpdate


router = APIRouter(prefix="/orders", tags=["orders"])
batch_router = APIRouter(prefix="/order-batches", tags=["orders"])

RequirePedidos = Depends(require_permission("pedidos"))


@router.get("", response_model=PaginatedResponse[OrderOut])
async def list_orders(
  claims: TokenClaims = RequirePedidos,
  session: AsyncSession = Depends(get_db_session),
  pagination: PaginationParams = Depends(pagination_params),
  stage: str | None = None,
  priority: str | None = None,
  client_name: str | None = None,
  product_name: str | None = None,
  deadline_from: date | None = None,
  deadline_to: date | None = None,
  sort: str = Query(default="created_at", pattern="^(created_at|deadline|order_code)$"),
  order: str = Query(default="desc", pattern="^(asc|desc)$"),
):
  return await service.list_for_org(
    session,
    organization_id=claims.org,
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


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(
  body: OrderCreate,
  claims: TokenClaims = RequirePedidos,
  session: AsyncSession = Depends(get_db_session),
):
  result = await service.create(session, organization_id=claims.org, body=body)
  await session.commit()
  return result


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
  order_id: str,
  claims: TokenClaims = RequirePedidos,
  session: AsyncSession = Depends(get_db_session),
):
  return await service.get_by_id(session, organization_id=claims.org, order_id=order_id)


@router.patch("/{order_id}", response_model=OrderOut)
async def update_order(
  order_id: str,
  body: OrderUpdate,
  claims: TokenClaims = RequirePedidos,
  session: AsyncSession = Depends(get_db_session),
):
  result = await service.update(
    session,
    organization_id=claims.org,
    order_id=order_id,
    body=body,
  )
  await session.commit()
  return result


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_order(
  order_id: str,
  claims: TokenClaims = RequirePedidos,
  session: AsyncSession = Depends(get_db_session),
):
  await service.delete(session, organization_id=claims.org, order_id=order_id)
  await session.commit()
  return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{order_id}/batches", response_model=OrderBatchOut, status_code=status.HTTP_201_CREATED)
async def create_order_batch(
  order_id: str,
  body: OrderBatchCreate,
  claims: TokenClaims = RequirePedidos,
  session: AsyncSession = Depends(get_db_session),
):
  result = await service.create_batch(
    session,
    organization_id=claims.org,
    order_id=order_id,
    body=body,
  )
  await session.commit()
  return result


@batch_router.patch("/{batch_id}", response_model=OrderBatchOut)
async def update_order_batch(
  batch_id: str,
  body: OrderBatchUpdate,
  claims: TokenClaims = RequirePedidos,
  session: AsyncSession = Depends(get_db_session),
):
  result = await service.update_batch(
    session,
    organization_id=claims.org,
    batch_id=batch_id,
    body=body,
  )
  await session.commit()
  return result


@batch_router.delete("/{batch_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_order_batch(
  batch_id: str,
  claims: TokenClaims = RequirePedidos,
  session: AsyncSession = Depends(get_db_session),
):
  await service.delete_batch(session, organization_id=claims.org, batch_id=batch_id)
  await session.commit()
  return Response(status_code=status.HTTP_204_NO_CONTENT)
