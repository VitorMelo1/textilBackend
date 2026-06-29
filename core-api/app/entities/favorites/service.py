from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.api.pagination import PaginatedResponse, PaginationParams

from . import repo
from .schemas import ProviderFavoriteOut


def to_out(row, provider) -> ProviderFavoriteOut:
  return ProviderFavoriteOut(
    id=row.id,
    organization_id=row.organization_id,
    provider_id=row.provider_id,
    user_id=row.user_id,
    provider_name=provider.name,
    provider_type=provider.provider_type,
    location=provider.location,
    rating=provider.rating,
    review_count=provider.review_count,
    verified=provider.verified,
    added_date=row.created_at,
    last_contact_at=row.last_contact_at,
  )


async def list_for_user(
  session: AsyncSession,
  *,
  organization_id: str,
  user_id: str,
  pagination: PaginationParams,
) -> PaginatedResponse[ProviderFavoriteOut]:
  total = await repo.count_favorites(session, organization_id=organization_id, user_id=user_id)
  rows = await repo.list_favorites(
    session,
    organization_id=organization_id,
    user_id=user_id,
    pagination=pagination,
  )
  return PaginatedResponse(
    items=[to_out(row, provider) for row, provider in rows],
    total=total,
    page=pagination.page,
    page_size=pagination.page_size,
  )


async def create(
  session: AsyncSession,
  *,
  organization_id: str,
  user_id: str,
  provider_id: str,
) -> ProviderFavoriteOut:
  provider = await repo.get_provider(session, provider_id)
  if provider is None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="provider not found")

  existing = await repo.get_favorite(
    session,
    organization_id=organization_id,
    user_id=user_id,
    provider_id=provider_id,
  )
  if existing is not None:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="provider already favorited")

  row = await repo.create_favorite(
    session,
    organization_id=organization_id,
    user_id=user_id,
    provider_id=provider_id,
  )
  return to_out(row, provider)


async def delete(
  session: AsyncSession,
  *,
  organization_id: str,
  user_id: str,
  provider_id: str,
) -> None:
  deleted = await repo.delete_favorite(
    session,
    organization_id=organization_id,
    user_id=user_id,
    provider_id=provider_id,
  )
  if not deleted:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="favorite not found")
