from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.api.pagination import PaginationParams
from shared.db.models import InterestRequest, Provider


async def get_provider(session: AsyncSession, provider_id: str) -> Provider | None:
  q = await session.execute(select(Provider).where(Provider.id == provider_id))
  return q.scalar_one_or_none()


async def count_interest_requests(
  session: AsyncSession,
  *,
  organization_id: str,
  status: str | None = None,
  provider_id: str | None = None,
) -> int:
  stmt = select(func.count()).select_from(InterestRequest).where(InterestRequest.organization_id == organization_id)
  if status is not None:
    stmt = stmt.where(InterestRequest.status == status)
  if provider_id is not None:
    stmt = stmt.where(InterestRequest.provider_id == provider_id)
  q = await session.execute(stmt)
  return int(q.scalar_one())


async def list_interest_requests(
  session: AsyncSession,
  *,
  organization_id: str,
  pagination: PaginationParams,
  status: str | None = None,
  provider_id: str | None = None,
) -> list[InterestRequest]:
  stmt = (
    select(InterestRequest)
    .where(InterestRequest.organization_id == organization_id)
    .order_by(InterestRequest.created_at.desc())
    .offset(pagination.offset)
    .limit(pagination.limit)
  )
  if status is not None:
    stmt = stmt.where(InterestRequest.status == status)
  if provider_id is not None:
    stmt = stmt.where(InterestRequest.provider_id == provider_id)
  q = await session.execute(stmt)
  return list(q.scalars().all())


async def get_interest_request_by_id(session: AsyncSession, *, interest_request_id: str) -> InterestRequest | None:
  q = await session.execute(select(InterestRequest).where(InterestRequest.id == interest_request_id))
  return q.scalar_one_or_none()


async def create_interest_request(
  session: AsyncSession,
  *,
  organization_id: str,
  provider_id: str,
  requester_user_id: str,
  message: str | None,
  target_city: str | None,
  target_state: str | None,
) -> InterestRequest:
  row = InterestRequest(
    organization_id=organization_id,
    provider_id=provider_id,
    requester_user_id=requester_user_id,
    message=message,
    target_city=target_city,
    target_state=target_state,
    status="pending",
  )
  session.add(row)
  await session.flush()
  return row
