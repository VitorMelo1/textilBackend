from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import get_settings
from shared.db.models import OAuthAccount, Organization, OrganizationMember, Plan, RefreshToken, Subscription, User
from shared.security.hashing import sha256_hex
from shared.security.passwords import hash_password


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
  q = await session.execute(select(User).where(User.email == email))
  return q.scalar_one_or_none()


async def create_local_user_with_org(
  session: AsyncSession,
  *,
  email: str,
  name: str,
  password: str,
  organization_name: str | None,
  user_type: str | None = None,
  business_profile: str | None = None,
) -> tuple[User, OrganizationMember]:
  user = User(
    email=email,
    name=name,
    password_hash=hash_password(password),
    user_type=user_type or "confeccao",
    business_profile=business_profile,
  )
  session.add(user)
  await session.flush()

  org = Organization(name=organization_name or f"{name} - Org")
  session.add(org)
  await session.flush()

  member = OrganizationMember(organization_id=org.id, user_id=user.id, role="owner", member_status="active")
  session.add(member)
  await session.flush()

  return user, member


async def get_oauth_account(session: AsyncSession, provider: str, provider_account_id: str) -> OAuthAccount | None:
  q = await session.execute(
    select(OAuthAccount).where(
      OAuthAccount.provider == provider, OAuthAccount.provider_account_id == provider_account_id
    )
  )
  return q.scalar_one_or_none()


async def create_organization_for_user(session: AsyncSession, user: User) -> Organization:
  org = Organization(name=user.name or "Minha organização")
  session.add(org)
  await session.flush()
  member = OrganizationMember(organization_id=org.id, user_id=user.id, role="owner", member_status="active")
  session.add(member)
  await session.flush()

  return org


async def ensure_default_plans(session: AsyncSession) -> None:
  defaults = [
    ("basic", "Basic"),
    ("professional", "Professional"),
    ("enterprise", "Enterprise"),
  ]
  existing = (await session.execute(select(Plan.key))).scalars().all()
  existing_set = set(existing)
  for key, name in defaults:
    if key not in existing_set:
      session.add(Plan(key=key, name=name))
  await session.flush()


async def get_plan_by_key(session: AsyncSession, key: str) -> Plan | None:
  q = await session.execute(select(Plan).where(Plan.key == key))
  return q.scalar_one_or_none()


async def get_first_org_for_user(session: AsyncSession, user_id: str) -> OrganizationMember | None:
  q = await session.execute(
    select(OrganizationMember)
    .where(OrganizationMember.user_id == user_id)
    .order_by(OrganizationMember.created_at.asc())
  )
  return q.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: str) -> User | None:
  q = await session.execute(select(User).where(User.id == user_id))
  return q.scalar_one_or_none()


async def get_subscription_plan_key(session: AsyncSession, organization_id: str) -> str | None:
  q = await session.execute(select(Subscription).where(Subscription.organization_id == organization_id))
  sub = q.scalar_one_or_none()
  if sub is None:
    return None
  if sub.status in {"cancelled", "expired", "incomplete_expired", "unpaid"}:
    return None
  plan_q = await session.execute(select(Plan).where(Plan.id == sub.plan_id))
  plan = plan_q.scalar_one_or_none()
  return plan.key if plan else None


async def get_org_membership(session: AsyncSession, *, user_id: str, organization_id: str) -> OrganizationMember | None:
  q = await session.execute(
    select(OrganizationMember).where(
      OrganizationMember.user_id == user_id,
      OrganizationMember.organization_id == organization_id,
    )
  )
  return q.scalar_one_or_none()


async def upsert_oauth_login(
  session: AsyncSession,
  *,
  provider: str,
  provider_account_id: str,
  email: str,
  name: str,
  token_data: dict | None = None,
) -> tuple[User, OrganizationMember]:
  acct = await get_oauth_account(session, provider, provider_account_id)
  if acct:
    q = await session.execute(select(User).where(User.id == acct.user_id))
    user = q.scalar_one()
  else:
    user = await get_user_by_email(session, email)
    if user is None:
      user = User(email=email, name=name)
      session.add(user)
      await session.flush()
      await create_organization_for_user(session, user)
    acct = OAuthAccount(user_id=user.id, provider=provider, provider_account_id=provider_account_id)
    session.add(acct)
    await session.flush()

  # opcional: salvar tokens do provedor (dev / debug)
  if token_data:
    acct.access_token = token_data.get("access_token")
    acct.refresh_token = token_data.get("refresh_token")
    acct.expires_at = token_data.get("expires_at")

  member = await get_first_org_for_user(session, user.id)
  if member is None:
    # fallback: garantir que existe org e membership
    await create_organization_for_user(session, user)
    member = await get_first_org_for_user(session, user.id)
    assert member is not None

  return user, member


async def create_refresh_token(
  session: AsyncSession, *, user_id: str, organization_id: str, raw_token: str
) -> RefreshToken:
  s = get_settings()
  expires_at = datetime.now(timezone.utc) + timedelta(days=s.REFRESH_TOKEN_TTL_DAYS)
  rt = RefreshToken(
    user_id=user_id,
    organization_id=organization_id,
    token_hash=sha256_hex(raw_token),
    expires_at=expires_at,
  )
  session.add(rt)
  await session.flush()
  return rt


async def revoke_refresh_token(session: AsyncSession, *, raw_token: str) -> bool:
  token_hash = sha256_hex(raw_token)
  q = await session.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
  rt = q.scalar_one_or_none()
  if rt is None or rt.revoked_at is not None:
    return False
  rt.revoked_at = datetime.now(timezone.utc)
  await session.flush()
  return True


async def get_refresh_token_record(session: AsyncSession, *, raw_token: str) -> RefreshToken | None:
  token_hash = sha256_hex(raw_token)
  q = await session.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
  return q.scalar_one_or_none()


async def get_org_by_id(session: AsyncSession, org_id: str) -> Organization | None:
  q = await session.execute(select(Organization).where(Organization.id == org_id))
  return q.scalar_one_or_none()


async def update_user_and_org(
  session: AsyncSession,
  *,
  user_id: str,
  org_id: str,
  name: str | None,
  company_name: str | None,
  phone: str | None,
  description: str | None,
) -> tuple[User, Organization] | None:
  user = await get_user_by_id(session, user_id)
  if user is None:
    return None
  org = await get_org_by_id(session, org_id)
  if org is None:
    return None
  if name is not None:
    user.name = name
  if company_name is not None:
    org.name = company_name
  if phone is not None:
    org.phone = phone
  if description is not None:
    org.description = description
  await session.flush()
  return user, org
