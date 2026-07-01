from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import Provider
from shared.db.session import get_db_session
from shared.security.jwt import TokenClaims
from shared.security.permissions import require_owner, require_permission

from .schemas import ProviderCreate, ProviderOut


router = APIRouter(prefix="/providers", tags=["network"])

RequireRede = Depends(require_permission("rede"))
RequireOwner = Depends(require_owner())


@router.get("", response_model=list[ProviderOut])
async def list_providers(claims: TokenClaims = RequireRede, session: AsyncSession = Depends(get_db_session)):
  q = await session.execute(
    select(Provider)
    .where(Provider.organization_id.is_not(None), Provider.organization_id != claims.org)
    .order_by(Provider.verified.desc(), Provider.rating.desc())
  )
  providers = q.scalars().all()
  return [
    ProviderOut(
      id=p.id,
      name=p.name,
      provider_type=p.provider_type,
      organization_id=p.organization_id,
      location=p.location,
      capacity=p.capacity,
      verified=p.verified,
      rating=p.rating,
      review_count=p.review_count,
      can_chat=bool(p.organization_id and p.organization_id != claims.org),
    )
    for p in providers
  ]


@router.post("", response_model=ProviderOut)
async def create_provider(
  body: ProviderCreate,
  claims: TokenClaims = RequireOwner,
  session: AsyncSession = Depends(get_db_session),
):
  p = Provider(
    organization_id=claims.org,
    owner_user_id=claims.sub,
    name=body.name,
    provider_type=body.provider_type,
    location=body.location,
    capacity=body.capacity,
    description=body.description,
    verified=False,
  )
  session.add(p)
  await session.flush()
  await session.commit()
  return ProviderOut(
    id=p.id,
    name=p.name,
    provider_type=p.provider_type,
    organization_id=p.organization_id,
    location=p.location,
    capacity=p.capacity,
    verified=p.verified,
    rating=p.rating,
    review_count=p.review_count,
    can_chat=False,
  )
