from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.api.pagination import PaginatedResponse, PaginationParams

from . import repo
from .schemas import InterestRequestCreate, InterestRequestOut, InterestRequestUpdate


ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
  "pending": {"matched", "rejected"},
  "matched": set(),
  "rejected": set(),
}


def validate_status_transition(current: str, new_status: str) -> None:
  allowed = ALLOWED_STATUS_TRANSITIONS.get(current, set())
  if new_status not in allowed:
    raise HTTPException(
      status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
      detail=f"invalid status transition: {current} -> {new_status}",
    )


def to_out(row) -> InterestRequestOut:
  return InterestRequestOut(
    id=row.id,
    organization_id=row.organization_id,
    provider_id=row.provider_id,
    requester_user_id=row.requester_user_id,
    message=row.message,
    target_city=row.target_city,
    target_state=row.target_state,
    status=row.status,
    created_at=row.created_at,
    updated_at=row.updated_at,
  )


async def list_for_org(
  session: AsyncSession,
  *,
  organization_id: str,
  pagination: PaginationParams,
  status_filter: str | None = None,
  provider_id: str | None = None,
) -> PaginatedResponse[InterestRequestOut]:
  if status_filter is not None and status_filter not in ALLOWED_STATUS_TRANSITIONS:
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="invalid status filter")
  total = await repo.count_interest_requests(
    session, organization_id=organization_id, status=status_filter, provider_id=provider_id
  )
  rows = await repo.list_interest_requests(
    session,
    organization_id=organization_id,
    pagination=pagination,
    status=status_filter,
    provider_id=provider_id,
  )
  return PaginatedResponse(
    items=[to_out(r) for r in rows],
    total=total,
    page=pagination.page,
    page_size=pagination.page_size,
  )


async def create(
  session: AsyncSession,
  *,
  organization_id: str,
  requester_user_id: str,
  body: InterestRequestCreate,
) -> InterestRequestOut:
  provider = await repo.get_provider(session, body.provider_id)
  if provider is None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="provider not found")

  row = await repo.create_interest_request(
    session,
    organization_id=organization_id,
    provider_id=body.provider_id,
    requester_user_id=requester_user_id,
    message=body.message,
    target_city=body.target_city,
    target_state=body.target_state,
  )
  return to_out(row)


async def get_by_id(session: AsyncSession, *, organization_id: str, interest_request_id: str) -> InterestRequestOut:
  row = await repo.get_interest_request_by_id(session, interest_request_id=interest_request_id)
  if row is None or row.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="interest request not found")
  return to_out(row)


async def update(
  session: AsyncSession,
  *,
  organization_id: str,
  interest_request_id: str,
  body: InterestRequestUpdate,
) -> InterestRequestOut:
  row = await repo.get_interest_request_by_id(session, interest_request_id=interest_request_id)
  if row is None or row.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="interest request not found")

  validate_status_transition(row.status, body.status)
  row.status = body.status
  await session.flush()
  return to_out(row)
