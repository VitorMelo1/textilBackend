from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.api.pagination import PaginationParams
from shared.db.models import OrganizationInvite, OrganizationMember, User


async def count_members(session: AsyncSession, *, organization_id: str) -> int:
  q = await session.execute(
    select(func.count()).select_from(OrganizationMember).where(OrganizationMember.organization_id == organization_id)
  )
  return int(q.scalar_one())


async def list_members(
  session: AsyncSession,
  *,
  organization_id: str,
  pagination: PaginationParams,
) -> list[tuple[OrganizationMember, User]]:
  q = await session.execute(
    select(OrganizationMember, User)
    .join(User, User.id == OrganizationMember.user_id)
    .where(OrganizationMember.organization_id == organization_id)
    .order_by(OrganizationMember.created_at.asc())
    .offset(pagination.offset)
    .limit(pagination.limit)
  )
  return list(q.all())


async def get_member_by_id(session: AsyncSession, *, member_id: str) -> OrganizationMember | None:
  q = await session.execute(select(OrganizationMember).where(OrganizationMember.id == member_id))
  return q.scalar_one_or_none()


async def get_member_with_user_by_id(
  session: AsyncSession,
  *,
  member_id: str,
) -> tuple[OrganizationMember, User] | None:
  q = await session.execute(
    select(OrganizationMember, User)
    .join(User, User.id == OrganizationMember.user_id)
    .where(OrganizationMember.id == member_id)
  )
  return q.first()


async def count_owners(session: AsyncSession, *, organization_id: str) -> int:
  q = await session.execute(
    select(func.count())
    .select_from(OrganizationMember)
    .where(OrganizationMember.organization_id == organization_id, OrganizationMember.role == "owner")
  )
  return int(q.scalar_one())


async def count_invites(
  session: AsyncSession,
  *,
  organization_id: str,
  status_filter: str | None = None,
) -> int:
  stmt = (
    select(func.count()).select_from(OrganizationInvite).where(OrganizationInvite.organization_id == organization_id)
  )
  if status_filter is not None:
    stmt = stmt.where(OrganizationInvite.status == status_filter)
  q = await session.execute(stmt)
  return int(q.scalar_one())


async def list_invites(
  session: AsyncSession,
  *,
  organization_id: str,
  pagination: PaginationParams,
  status_filter: str | None = None,
) -> list[OrganizationInvite]:
  stmt = (
    select(OrganizationInvite)
    .where(OrganizationInvite.organization_id == organization_id)
    .order_by(OrganizationInvite.created_at.desc())
    .offset(pagination.offset)
    .limit(pagination.limit)
  )
  if status_filter is not None:
    stmt = stmt.where(OrganizationInvite.status == status_filter)
  q = await session.execute(stmt)
  return list(q.scalars().all())


async def create_invite(
  session: AsyncSession,
  *,
  organization_id: str,
  email: str,
  job_title: str | None,
  permissions_csv: str,
  invited_by_user_id: str,
  token_hash: str,
  expires_at: datetime,
) -> OrganizationInvite:
  row = OrganizationInvite(
    organization_id=organization_id,
    email=email,
    job_title=job_title,
    permissions_csv=permissions_csv,
    invited_by_user_id=invited_by_user_id,
    status="pending",
    token_hash=token_hash,
    expires_at=expires_at,
  )
  session.add(row)
  await session.flush()
  return row


async def get_invite_by_id(session: AsyncSession, *, invite_id: str) -> OrganizationInvite | None:
  q = await session.execute(select(OrganizationInvite).where(OrganizationInvite.id == invite_id))
  return q.scalar_one_or_none()


async def get_member_for_org_user(
  session: AsyncSession,
  *,
  organization_id: str,
  user_id: str,
) -> OrganizationMember | None:
  q = await session.execute(
    select(OrganizationMember).where(
      OrganizationMember.organization_id == organization_id,
      OrganizationMember.user_id == user_id,
    )
  )
  return q.scalar_one_or_none()


async def create_member(
  session: AsyncSession,
  *,
  organization_id: str,
  user_id: str,
  role: str,
  job_title: str | None,
  member_status: str,
  permissions_csv: str,
) -> OrganizationMember:
  row = OrganizationMember(
    organization_id=organization_id,
    user_id=user_id,
    role=role,
    job_title=job_title,
    member_status=member_status,
    permissions_csv=permissions_csv,
  )
  session.add(row)
  await session.flush()
  return row
