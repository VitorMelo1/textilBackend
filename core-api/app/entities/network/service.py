from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import Provider


def provider_type_from_profile(business_profile: str | None, user_type: str | None = None) -> str:
  if business_profile == "solo":
    return user_type or "Prestador Solo"
  if business_profile == "industry":
    return "Indústria"
  return user_type or "Atelier"


async def upsert_provider_profile_for_org(
  session: AsyncSession,
  *,
  organization_id: str,
  owner_user_id: str,
  name: str,
  business_profile: str | None,
  user_type: str | None = None,
  description: str | None = None,
) -> Provider:
  q = await session.execute(select(Provider).where(Provider.organization_id == organization_id))
  provider = q.scalar_one_or_none()
  if provider is None:
    provider = Provider(
      organization_id=organization_id,
      owner_user_id=owner_user_id,
      name=name,
      provider_type=provider_type_from_profile(business_profile, user_type),
      description=description,
      verified=False,
    )
    session.add(provider)
  else:
    provider.owner_user_id = provider.owner_user_id or owner_user_id
    provider.name = name
    provider.provider_type = provider_type_from_profile(business_profile, user_type)
    provider.description = description
  await session.flush()
  return provider
