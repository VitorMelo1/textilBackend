from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import Provider, Review
from shared.db.session import get_db_session
from shared.security.jwt import TokenClaims
from shared.security.permissions import require_permission

from .schemas import ReviewCreate, ReviewOut
from .service import refresh_provider_reputation


router = APIRouter(prefix="/reviews", tags=["reviews"])
RequireRede = Depends(require_permission("rede"))


def _to_out(row: Review, provider_name: str | None) -> ReviewOut:
  return ReviewOut(
    id=row.id,
    organization_id=row.organization_id,
    provider_id=row.provider_id,
    provider_name=provider_name,
    author_user_id=row.author_user_id,
    rating=row.rating,
    comment=row.comment,
    quality=row.quality,
    deadline=row.deadline,
    communication=row.communication,
    created_at=row.created_at.isoformat() if row.created_at else None,
  )


@router.get("", response_model=list[ReviewOut])
async def list_reviews(
  claims: TokenClaims = RequireRede,
  session: AsyncSession = Depends(get_db_session),
):
  q = await session.execute(
    select(Review, Provider.name)
    .outerjoin(Provider, Review.provider_id == Provider.id)
    .where(Review.organization_id == claims.org)
    .order_by(Review.created_at.desc())
  )
  rows = q.all()
  return [_to_out(review, provider_name) for review, provider_name in rows]


@router.post("", response_model=ReviewOut)
async def create_review(
  body: ReviewCreate,
  claims: TokenClaims = RequireRede,
  session: AsyncSession = Depends(get_db_session),
):
  # validate provider exists first
  prov = await session.get(Provider, body.provider_id)
  if prov is None:
    raise HTTPException(status_code=404, detail="provider not found")
  r = Review(
    organization_id=claims.org,
    provider_id=body.provider_id,
    author_user_id=claims.sub,
    rating=body.rating,
    comment=body.comment,
    quality=body.quality,
    deadline=body.deadline,
    communication=body.communication,
  )
  session.add(r)
  await session.flush()
  await refresh_provider_reputation(session, prov)
  await session.commit()
  return _to_out(r, prov.name)
