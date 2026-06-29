from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.api.pagination import PaginatedResponse, PaginationParams, pagination_params
from shared.db.session import get_db_session
from shared.security.jwt import TokenClaims
from shared.security.permissions import require_permission

from . import service
from .schemas import InterestRequestCreate, InterestRequestOut, InterestRequestUpdate


router = APIRouter(prefix="/interest-requests", tags=["interest_requests"])

RequireRede = Depends(require_permission("rede"))


@router.get("", response_model=PaginatedResponse[InterestRequestOut])
async def list_interest_requests(
  claims: TokenClaims = RequireRede,
  session: AsyncSession = Depends(get_db_session),
  pagination: PaginationParams = Depends(pagination_params),
  status_filter: str | None = Query(default=None, alias="status"),
  provider_id: str | None = None,
):
  return await service.list_for_org(
    session,
    organization_id=claims.org,
    pagination=pagination,
    status_filter=status_filter,
    provider_id=provider_id,
  )


@router.post("", response_model=InterestRequestOut, status_code=status.HTTP_201_CREATED)
async def create_interest_request(
  body: InterestRequestCreate,
  claims: TokenClaims = RequireRede,
  session: AsyncSession = Depends(get_db_session),
):
  result = await service.create(
    session,
    organization_id=claims.org,
    requester_user_id=claims.sub,
    body=body,
  )
  await session.commit()
  return result


@router.get("/{interest_request_id}", response_model=InterestRequestOut)
async def get_interest_request(
  interest_request_id: str,
  claims: TokenClaims = RequireRede,
  session: AsyncSession = Depends(get_db_session),
):
  return await service.get_by_id(session, organization_id=claims.org, interest_request_id=interest_request_id)


@router.patch("/{interest_request_id}", response_model=InterestRequestOut)
async def update_interest_request(
  interest_request_id: str,
  body: InterestRequestUpdate,
  claims: TokenClaims = RequireRede,
  session: AsyncSession = Depends(get_db_session),
):
  result = await service.update(
    session,
    organization_id=claims.org,
    interest_request_id=interest_request_id,
    body=body,
  )
  await session.commit()
  return result
