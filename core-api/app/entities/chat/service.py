from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import OrganizationMember

from . import repo


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


async def get_or_create_provider_conversation(
  session: AsyncSession,
  *,
  requester_organization_id: str,
  requester_user_id: str,
  provider_id: str,
  interest_request_id: str | None = None,
):
  provider = await repo.get_provider(session, provider_id)
  if provider is None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="provider not found")
  if not provider.organization_id:
    raise HTTPException(
      status_code=status.HTTP_409_CONFLICT,
      detail="provider is not linked to an active organization",
    )
  if provider.organization_id == requester_organization_id:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="cannot chat with your own provider profile")

  existing = await repo.get_provider_conversation(
    session,
    organization_id=requester_organization_id,
    provider_id=provider_id,
  )
  if existing is not None:
    return existing

  recipient_user_ids = await repo.list_active_chat_member_user_ids(session, organization_id=provider.organization_id)
  if not recipient_user_ids:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="provider organization has no active members")

  members = [(requester_organization_id, requester_user_id)]
  members.extend((provider.organization_id, user_id) for user_id in recipient_user_ids)
  return await repo.create_provider_conversation(
    session,
    organization_id=requester_organization_id,
    provider_id=provider_id,
    interest_request_id=interest_request_id,
    title=provider.name,
    members=members,
  )


async def get_or_create_interest_conversation(
  session: AsyncSession,
  *,
  requester_organization_id: str,
  requester_user_id: str,
  interest_request_id: str,
):
  interest = await repo.get_interest_request(session, interest_request_id)
  if interest is None or interest.organization_id != requester_organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="interest request not found")
  existing = await repo.get_interest_conversation(
    session,
    organization_id=requester_organization_id,
    interest_request_id=interest_request_id,
  )
  if existing is not None:
    return existing

  provider = await repo.get_provider(session, interest.provider_id)
  if provider is None:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="provider not found")
  if not provider.organization_id:
    raise HTTPException(
      status_code=status.HTTP_409_CONFLICT,
      detail="provider is not linked to an active organization",
    )
  if provider.organization_id == requester_organization_id:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="cannot chat with your own provider profile")
  recipient_user_ids = await repo.list_active_chat_member_user_ids(session, organization_id=provider.organization_id)
  if not recipient_user_ids:
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="provider organization has no active members")
  members = [(requester_organization_id, requester_user_id)]
  members.extend((provider.organization_id, user_id) for user_id in recipient_user_ids)
  return await repo.create_provider_conversation(
    session,
    provider_id=interest.provider_id,
    organization_id=requester_organization_id,
    title=provider.name,
    members=members,
    interest_request_id=interest_request_id,
  )


async def get_or_create_order_conversation(
  session: AsyncSession,
  *,
  organization_id: str,
  requester_user_id: str,
  order_id: str,
):
  order = await repo.get_order(session, order_id)
  if order is None or order.organization_id != organization_id:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="order not found")
  existing = await repo.get_order_conversation(session, organization_id=organization_id, order_id=order_id)
  if existing is not None:
    return existing
  member_user_ids = await repo.list_active_chat_member_user_ids(session, organization_id=organization_id)
  if requester_user_id not in member_user_ids:
    member_user_ids.insert(0, requester_user_id)
  return await repo.create_order_conversation(
    session,
    organization_id=organization_id,
    order_id=order_id,
    title=f"Pedido {order.order_code}",
    members=member_user_ids,
  )
