from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "core-api"))

from app.entities.network.service import upsert_provider_profile_for_org  # noqa: E402
from shared.db.models import Organization, OrganizationMember, User  # noqa: E402
from shared.db.session import SESSIONMAKER  # noqa: E402


async def main() -> int:
  updated = 0
  async with SESSIONMAKER() as session:
    rows = await session.execute(
      select(Organization, User)
      .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
      .join(User, User.id == OrganizationMember.user_id)
      .where(OrganizationMember.role == "owner")
      .order_by(Organization.created_at.asc())
    )
    for organization, user in rows.all():
      await upsert_provider_profile_for_org(session, organization=organization, user=user)
      updated += 1
    await session.commit()
  print(f"provider profiles backfilled: {updated}")
  return 0


if __name__ == "__main__":
  raise SystemExit(asyncio.run(main()))
