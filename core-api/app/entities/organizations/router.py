from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import Organization
from shared.db.session import get_db_session
from shared.security.deps import require_auth_claims


router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("/current")
async def get_current_org(claims=Depends(require_auth_claims), session: AsyncSession = Depends(get_db_session)) -> dict:
  q = await session.execute(select(Organization).where(Organization.id == claims.org))
  org = q.scalar_one_or_none()
  if org is None:
    raise HTTPException(status_code=404, detail="organization not found")
  return {"id": org.id, "name": org.name}
