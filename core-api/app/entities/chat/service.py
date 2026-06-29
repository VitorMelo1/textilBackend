from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import OrganizationMember


async def find_missing_org_members(session: AsyncSession, *, organization_id: str, user_ids: set[str]) -> set[str]:
  """Retorna os user_ids que NÃO são membros da organização (valida convites de conversa)."""
  if not user_ids:
    return set()
  q = await session.execute(
    select(OrganizationMember.user_id).where(
      OrganizationMember.organization_id == organization_id,
      OrganizationMember.user_id.in_(user_ids),
    )
  )
  found = {row[0] for row in q}
  return user_ids - found
