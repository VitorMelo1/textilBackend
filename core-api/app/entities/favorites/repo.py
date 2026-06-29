from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.api.pagination import PaginationParams
from shared.db.models import Provider, ProviderFavorite


async def get_provider(session: AsyncSession, provider_id: str) -> Provider | None:
  q = await session.execute(select(Provider).where(Provider.id == provider_id))
  return q.scalar_one_or_none()


async def get_favorite(
  session: AsyncSession,
  *,
  organization_id: str,
  user_id: str,
  provider_id: str,
) -> ProviderFavorite | None:
  q = await session.execute(
    select(ProviderFavorite).where(
      ProviderFavorite.organization_id == organization_id,
      ProviderFavorite.user_id == user_id,
      ProviderFavorite.provider_id == provider_id,
    )
  )
  return q.scalar_one_or_none()


async def count_favorites(session: AsyncSession, *, organization_id: str, user_id: str) -> int:
  q = await session.execute(
    select(func.count())
    .select_from(ProviderFavorite)
    .where(ProviderFavorite.organization_id == organization_id, ProviderFavorite.user_id == user_id)
  )
  return int(q.scalar_one())


async def list_favorites(
  session: AsyncSession,
  *,
  organization_id: str,
  user_id: str,
  pagination: PaginationParams,
) -> list[tuple[ProviderFavorite, Provider]]:
  q = await session.execute(
    select(ProviderFavorite, Provider)
    .join(Provider, Provider.id == ProviderFavorite.provider_id)
    .where(ProviderFavorite.organization_id == organization_id, ProviderFavorite.user_id == user_id)
    .order_by(ProviderFavorite.created_at.desc())
    .offset(pagination.offset)
    .limit(pagination.limit)
  )
  return list(q.all())


async def create_favorite(
  session: AsyncSession,
  *,
  organization_id: str,
  user_id: str,
  provider_id: str,
) -> ProviderFavorite:
  row = ProviderFavorite(organization_id=organization_id, user_id=user_id, provider_id=provider_id)
  session.add(row)
  await session.flush()
  return row


async def delete_favorite(
  session: AsyncSession,
  *,
  organization_id: str,
  user_id: str,
  provider_id: str,
) -> bool:
  row = await get_favorite(
    session,
    organization_id=organization_id,
    user_id=user_id,
    provider_id=provider_id,
  )
  if row is None:
    return False
  await session.delete(row)
  await session.flush()
  return True
