from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import OrganizationMember, Plan, Subscription, User
from shared.security.deps import require_auth_claims
from shared.security.jwt import TokenClaims

BusinessProfile = str
PlanTier = str

MODULE_ENTITLEMENT_MATRIX: dict[BusinessProfile, dict[PlanTier, set[str]]] = {
  "solo": {
    "basic": {"pedidos", "rede", "chat", "financeiro"},
    "professional": {"pedidos", "rede", "chat", "financeiro"},
    "enterprise": {"pedidos", "rede", "chat", "fichas", "financeiro"},
  },
  "atelier": {
    "basic": {"pedidos", "estoque", "custos", "rede", "chat", "financeiro"},
    "professional": {"pedidos", "estoque", "custos", "rede", "chat", "fichas", "financeiro"},
    "enterprise": {"pedidos", "estoque", "custos", "rede", "chat", "fichas", "team", "configuracoes", "financeiro"},
  },
  "industry": {
    "basic": {"pedidos", "estoque", "custos", "rede", "chat", "financeiro"},
    "professional": {"pedidos", "estoque", "custos", "rede", "chat", "fichas", "configuracoes", "financeiro"},
    "enterprise": {"pedidos", "estoque", "custos", "rede", "chat", "fichas", "team", "configuracoes", "financeiro"},
  },
}

ENTITLED_SLUGS = {slug for plans in MODULE_ENTITLEMENT_MATRIX.values() for slugs in plans.values() for slug in slugs}


def parse_permissions_csv(permissions_csv: str) -> set[str]:
  if not permissions_csv:
    return set()
  return {slug.strip() for slug in permissions_csv.split(",") if slug.strip()}


def has_permission(*, role: str | None, permissions_csv: str, slug: str) -> bool:
  if role == "owner":
    return True
  return slug in parse_permissions_csv(permissions_csv)


def has_entitlement(*, business_profile: str | None, plan_key: str | None, slug: str) -> bool:
  if slug not in ENTITLED_SLUGS:
    return True
  if not business_profile or not plan_key:
    return False
  return slug in MODULE_ENTITLEMENT_MATRIX.get(business_profile, {}).get(plan_key, set())


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


async def get_business_profile_for_org_member(session: AsyncSession, claims: TokenClaims) -> str | None:
  current_user_q = await session.execute(select(User.business_profile).where(User.id == claims.sub))
  current_profile = current_user_q.scalar_one_or_none()
  if current_profile:
    return current_profile

  owner_q = await session.execute(
    select(User.business_profile)
    .join(OrganizationMember, OrganizationMember.user_id == User.id)
    .where(
      OrganizationMember.organization_id == claims.org,
      OrganizationMember.role == "owner",
      OrganizationMember.member_status == "active",
      User.business_profile.is_not(None),
    )
    .limit(1)
  )
  return owner_q.scalar_one_or_none()


async def get_plan_key_for_org(session: AsyncSession, organization_id: str) -> str | None:
  plan_q = await session.execute(
    select(Plan.key)
    .join(Subscription, Subscription.plan_id == Plan.id)
    .where(Subscription.organization_id == organization_id, Subscription.status.in_(("active", "trialing")))
  )
  return plan_q.scalar_one_or_none()


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
    business_profile = await get_business_profile_for_org_member(session, claims)
    plan_key = await get_plan_key_for_org(session, claims.org)
    if not has_entitlement(business_profile=business_profile, plan_key=plan_key, slug=slug):
      raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"module unavailable for current plan/profile: {slug}",
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


def require_owner_entitled(slug: str) -> Callable[..., TokenClaims]:
  from shared.db.session import get_db_session

  async def _dependency(
    claims: TokenClaims = Depends(require_auth_claims),
    session: AsyncSession = Depends(get_db_session),
  ) -> TokenClaims:
    member = await get_active_membership(session, claims)
    if member.role != "owner":
      raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="owner role required")
    business_profile = await get_business_profile_for_org_member(session, claims)
    plan_key = await get_plan_key_for_org(session, claims.org)
    if not has_entitlement(business_profile=business_profile, plan_key=plan_key, slug=slug):
      raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"module unavailable for current plan/profile: {slug}",
      )
    return claims

  return _dependency
