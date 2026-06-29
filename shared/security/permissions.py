from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import OrganizationMember
from shared.security.deps import require_auth_claims
from shared.security.jwt import TokenClaims


def parse_permissions_csv(permissions_csv: str) -> set[str]:
  if not permissions_csv:
    return set()
  return {slug.strip() for slug in permissions_csv.split(",") if slug.strip()}


def has_permission(*, role: str | None, permissions_csv: str, slug: str) -> bool:
  if role == "owner":
    return True
  return slug in parse_permissions_csv(permissions_csv)


async def get_active_membership(session: AsyncSession, claims: TokenClaims) -> OrganizationMember:
  q = await session.execute(
    select(OrganizationMember).where(
      OrganizationMember.user_id == claims.sub,
      OrganizationMember.organization_id == claims.org,
    )
  )
  member = q.scalar_one_or_none()
  if member is None:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="no organization membership")
  if member.member_status != "active":
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="member inactive")
  return member


def require_permission(slug: str) -> Callable[..., TokenClaims]:
  from shared.db.session import get_db_session

  async def _dependency(
    claims: TokenClaims = Depends(require_auth_claims),
    session: AsyncSession = Depends(get_db_session),
  ) -> TokenClaims:
    member = await get_active_membership(session, claims)
    if not has_permission(role=member.role, permissions_csv=member.permissions_csv, slug=slug):
      raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"permission denied: {slug}",
      )
    return claims

  return _dependency


def require_owner() -> Callable[..., TokenClaims]:
  from shared.db.session import get_db_session

  async def _dependency(
    claims: TokenClaims = Depends(require_auth_claims),
    session: AsyncSession = Depends(get_db_session),
  ) -> TokenClaims:
    member = await get_active_membership(session, claims)
    if member.role != "owner":
      raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="owner role required")
    return claims

  return _dependency
