from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from shared.security.hashing import new_token_urlsafe
from shared.security.jwt import create_access_token

from . import repo


async def issue_tokens_for_user(
  session: AsyncSession, *, user_id: str, organization_id: str, role: str | None
) -> tuple[str, str]:
  access = create_access_token(subject=user_id, organization_id=organization_id, role=role)
  refresh_raw = new_token_urlsafe(32)
  await repo.create_refresh_token(session, user_id=user_id, organization_id=organization_id, raw_token=refresh_raw)
  return access, refresh_raw


async def rotate_refresh_token(session: AsyncSession, *, raw_refresh_token: str) -> tuple[str, str] | None:
  rt = await repo.get_refresh_token_record(session, raw_token=raw_refresh_token)
  if rt is None:
    return None
  if rt.revoked_at is not None:
    return None
  if rt.expires_at <= datetime.now(timezone.utc):
    return None

  # revoke old + issue new pair
  await repo.revoke_refresh_token(session, raw_token=raw_refresh_token)
  member = await repo.get_org_membership(session, user_id=rt.user_id, organization_id=rt.organization_id)
  if member is None or member.member_status != "active":
    return None
  access, new_refresh = await issue_tokens_for_user(
    session, user_id=rt.user_id, organization_id=rt.organization_id, role=member.role
  )
  return access, new_refresh
