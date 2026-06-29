from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.api.pagination import PaginatedResponse, PaginationParams, pagination_params
from shared.db.session import get_db_session
from shared.security.jwt import TokenClaims
from shared.security.permissions import require_permission

from . import service
from .schemas import ProviderFavoriteCreate, ProviderFavoriteOut


router = APIRouter(prefix="/provider-favorites", tags=["favorites"])

RequireRede = Depends(require_permission("rede"))


@router.get("", response_model=PaginatedResponse[ProviderFavoriteOut])
async def list_provider_favorites(
  claims: TokenClaims = RequireRede,
  session: AsyncSession = Depends(get_db_session),
  pagination: PaginationParams = Depends(pagination_params),
):
  return await service.list_for_user(
    session,
    organization_id=claims.org,
    user_id=claims.sub,
    pagination=pagination,
  )


@router.post("", response_model=ProviderFavoriteOut, status_code=status.HTTP_201_CREATED)
async def create_provider_favorite(
  body: ProviderFavoriteCreate,
  claims: TokenClaims = RequireRede,
  session: AsyncSession = Depends(get_db_session),
):
  result = await service.create(
    session,
    organization_id=claims.org,
    user_id=claims.sub,
    provider_id=body.provider_id,
  )
  await session.commit()
  return result


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_provider_favorite(
  provider_id: str,
  claims: TokenClaims = RequireRede,
  session: AsyncSession = Depends(get_db_session),
):
  await service.delete(
    session,
    organization_id=claims.org,
    user_id=claims.sub,
    provider_id=provider_id,
  )
  await session.commit()
  return Response(status_code=status.HTTP_204_NO_CONTENT)
