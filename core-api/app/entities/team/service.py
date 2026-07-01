from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.api.pagination import PaginatedResponse, PaginationParams
from shared.security.hashing import new_token_urlsafe, sha256_hex
from shared.security.permissions import parse_permissions_csv

from . import repo
from .schemas import InviteCreate, InviteOut, MemberOut, MemberUpdate


INVITE_TTL_DAYS = 7
VALID_INVITE_STATUSES = {"pending", "accepted", "revoked", "expired"}


def permissions_to_csv(permissions: list[str]) -> str:
  return ",".join(sorted(set(permissions)))


def member_to_out(member, user) -> MemberOut:
  return MemberOut(
    id=member.id,
    user_id=member.user_id,
    email=user.email,
    name=user.name,
    role=member.role,
    job_title=member.job_title,
    member_status=member.member_status,
    permissions=sorted(parse_permissions_csv(member.permissions_csv)),
    last_active_at=member.last_active_at,
    created_at=member.created_at,
  )


def invite_to_out(invite) -> InviteOut:
  return InviteOut(
    id=invite.id,
    organization_id=invite.organization_id,
    email=invite.email,
    job_title=invite.job_title,
    permissions=sorted(parse_permissions_csv(invite.permissions_csv)),
    invited_by_user_id=invite.invited_by_user_id,
    status=invite.status,
    expires_at=invite.expires_at,
    accepted_at=invite.accepted_at,
    created_at=invite.created_at,
  )


def invite_delivery_out(invite: InviteOut, *, raw_token: str, email_delivery_enabled: bool) -> InviteOut:
  if email_delivery_enabled:
    return invite.model_copy(update={"acceptance_token": None})
  return invite.model_copy(update={"acceptance_token": raw_token})


async def list_members(
  session: AsyncSession,
  *,
  organization_id: str,
  pagination: PaginationParams,
) -> PaginatedResponse[MemberOut]:
  total = await repo.count_members(session, organization_id=organization_id)
  rows = await repo.list_members(session, organization_id=organization_id, pagination=pagination)
  return PaginatedResponse(
    items=[member_to_out(member, user) for member, user in rows],
    total=total,
    page=pagination.page,
    page_size=pagination.page_size,
  )


async def update_member(
  session: AsyncSession,
  *,
  organization_id: str,
  member_id: str,
  body: MemberUpdate,
) -> MemberOut:
  row = await repo.get_member_by_id(session, member_id=member_id)
  if row is None or row.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="member not found")

  if body.role is not None and row.role == "owner" and body.role != "owner":
    owners = await repo.count_owners(session, organization_id=organization_id)
    if owners <= 1:
      raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cannot remove last owner")

  if body.role is not None:
    row.role = body.role
  if body.job_title is not None:
    row.job_title = body.job_title
  if body.member_status is not None:
    row.member_status = body.member_status
  if body.permissions is not None:
    row.permissions_csv = permissions_to_csv(body.permissions)

  await session.flush()
  row_with_user = await repo.get_member_with_user_by_id(session, member_id=row.id)
  if row_with_user is None:
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="member updated but not found")
  member, user = row_with_user
  return member_to_out(member, user)


async def delete_member(
  session: AsyncSession,
  *,
  organization_id: str,
  member_id: str,
) -> None:
  row = await repo.get_member_by_id(session, member_id=member_id)
  if row is None or row.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="member not found")
  if row.role == "owner":
    owners = await repo.count_owners(session, organization_id=organization_id)
    if owners <= 1:
      raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cannot remove last owner")
  await session.delete(row)
  await session.flush()


async def create_invite(
  session: AsyncSession,
  *,
  organization_id: str,
  invited_by_user_id: str,
  body: InviteCreate,
) -> tuple[InviteOut, str]:
  raw_token = new_token_urlsafe(32)
  token_hash = sha256_hex(raw_token)
  expires_at = datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS)
  row = await repo.create_invite(
    session,
    organization_id=organization_id,
    email=body.email.lower().strip(),
    job_title=body.job_title,
    permissions_csv=permissions_to_csv(body.permissions),
    invited_by_user_id=invited_by_user_id,
    token_hash=token_hash,
    expires_at=expires_at,
  )
  return invite_to_out(row), raw_token


async def list_invites(
  session: AsyncSession,
  *,
  organization_id: str,
  pagination: PaginationParams,
  status_filter: str | None = "pending",
) -> PaginatedResponse[InviteOut]:
  if status_filter is not None and status_filter not in VALID_INVITE_STATUSES:
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="invalid invite status filter")
  total = await repo.count_invites(session, organization_id=organization_id, status_filter=status_filter)
  rows = await repo.list_invites(
    session,
    organization_id=organization_id,
    pagination=pagination,
    status_filter=status_filter,
  )
  return PaginatedResponse(
    items=[invite_to_out(row) for row in rows],
    total=total,
    page=pagination.page,
    page_size=pagination.page_size,
  )


async def accept_invite(
  session: AsyncSession,
  *,
  invite_id: str,
  token: str,
  current_user_id: str,
) -> dict[str, str]:
  invite = await repo.get_invite_by_id(session, invite_id=invite_id)
  if invite is None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invite not found")
  if invite.status != "pending":
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invite not pending")
  if invite.expires_at <= datetime.now(timezone.utc):
    invite.status = "expired"
    await session.flush()
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invite expired")
  if invite.token_hash != sha256_hex(token):
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid invite token")

  existing = await repo.get_member_for_org_user(
    session,
    organization_id=invite.organization_id,
    user_id=current_user_id,
  )
  if existing is None:
    existing = await repo.create_member(
      session,
      organization_id=invite.organization_id,
      user_id=current_user_id,
      role="member",
      job_title=invite.job_title,
      member_status="active",
      permissions_csv=invite.permissions_csv,
    )

  invite.status = "accepted"
  invite.accepted_at = datetime.now(timezone.utc)
  await session.flush()
  return {"member_id": existing.id, "organization_id": invite.organization_id}


async def cancel_invite(
  session: AsyncSession,
  *,
  organization_id: str,
  invite_id: str,
) -> dict[str, str]:
  invite = await repo.get_invite_by_id(session, invite_id=invite_id)
  if invite is None or invite.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="invite not found")
  if invite.status != "pending":
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invite is not pending")
  invite.status = "revoked"
  await session.flush()
  return {"status": "revoked"}
