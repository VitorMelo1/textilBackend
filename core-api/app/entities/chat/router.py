from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import Conversation, ConversationMember
from shared.db.session import get_db_session
from shared.security.jwt import TokenClaims
from shared.security.permissions import require_permission

from . import repo
from .schemas import ConversationCreate, ConversationOut
from .service import (
  find_missing_org_members,
  get_or_create_interest_conversation,
  get_or_create_order_conversation,
  get_or_create_provider_conversation,
)


router = APIRouter(prefix="/conversations", tags=["chat"])

# Matriz de permissões (docs/17): slug "chat" cobre conversations, messages e websocket.
RequireChat = Depends(require_permission("chat"))


async def _conversation_out(
  session: AsyncSession,
  conversation: Conversation,
  member: ConversationMember | None = None,
) -> ConversationOut:
  unread_count = 0
  last_message = None
  if member is not None:
    unread_count, last_message = await repo.get_conversation_meta(
      session,
      conversation_id=conversation.id,
      member=member,
    )
  return ConversationOut(
    id=conversation.id,
    organization_id=conversation.organization_id,
    title=conversation.title,
    provider_id=conversation.provider_id,
    interest_request_id=conversation.interest_request_id,
    order_id=conversation.order_id,
    unread_count=unread_count,
    last_message_body=(last_message.body if last_message else None),
    last_message_at=(last_message.created_at.isoformat() if last_message else None),
  )


@router.get("", response_model=list[ConversationOut])
async def list_conversations(claims: TokenClaims = RequireChat, session: AsyncSession = Depends(get_db_session)):
  q = await session.execute(
    select(Conversation)
    .join(ConversationMember, ConversationMember.conversation_id == Conversation.id)
    .where(ConversationMember.organization_id == claims.org, ConversationMember.user_id == claims.sub)
    .order_by(Conversation.created_at.desc())
  )
  rows = q.scalars().all()
  result: list[ConversationOut] = []
  for conversation in rows:
    member = await repo.get_my_membership(
      session,
      organization_id=claims.org,
      conversation_id=conversation.id,
      user_id=claims.sub,
    )
    result.append(await _conversation_out(session, conversation, member))
  return result


@router.post("", response_model=ConversationOut)
async def create_conversation(
  body: ConversationCreate,
  claims: TokenClaims = RequireChat,
  session: AsyncSession = Depends(get_db_session),
):
  requested = {uid for uid in body.member_user_ids if uid}
  if not requested:
    raise HTTPException(status_code=422, detail="member_user_ids must include at least one recipient")
  missing = await find_missing_org_members(session, organization_id=claims.org, user_ids=requested)
  if missing:
    raise HTTPException(
      status_code=422,
      detail="member_user_ids must be active members of the organization",
    )

  conv = Conversation(organization_id=claims.org, title=body.title)
  session.add(conv)
  await session.flush()

  # always include author
  member_ids = {claims.sub, *requested}
  for uid in member_ids:
    session.add(ConversationMember(organization_id=claims.org, conversation_id=conv.id, user_id=uid, role="member"))
  await session.commit()
  member = await repo.get_my_membership(session, organization_id=claims.org, conversation_id=conv.id, user_id=claims.sub)
  return await _conversation_out(session, conv, member)


@router.post("/provider/{provider_id}", response_model=ConversationOut)
async def start_provider_conversation(
  provider_id: str,
  claims: TokenClaims = RequireChat,
  session: AsyncSession = Depends(get_db_session),
):
  conv = await get_or_create_provider_conversation(
    session,
    requester_organization_id=claims.org,
    requester_user_id=claims.sub,
    provider_id=provider_id,
  )
  await session.commit()
  member = await repo.get_my_membership(session, organization_id=claims.org, conversation_id=conv.id, user_id=claims.sub)
  return await _conversation_out(session, conv, member)


@router.post("/interest/{interest_request_id}", response_model=ConversationOut)
async def start_interest_conversation(
  interest_request_id: str,
  claims: TokenClaims = RequireChat,
  session: AsyncSession = Depends(get_db_session),
):
  conv = await get_or_create_interest_conversation(
    session,
    requester_organization_id=claims.org,
    requester_user_id=claims.sub,
    interest_request_id=interest_request_id,
  )
  await session.commit()
  member = await repo.get_my_membership(session, organization_id=claims.org, conversation_id=conv.id, user_id=claims.sub)
  return await _conversation_out(session, conv, member)


@router.post("/orders/{order_id}", response_model=ConversationOut)
async def start_order_conversation(
  order_id: str,
  claims: TokenClaims = RequireChat,
  session: AsyncSession = Depends(get_db_session),
):
  conv = await get_or_create_order_conversation(
    session,
    organization_id=claims.org,
    requester_user_id=claims.sub,
    order_id=order_id,
  )
  await session.commit()
  member = await repo.get_my_membership(session, organization_id=claims.org, conversation_id=conv.id, user_id=claims.sub)
  return await _conversation_out(session, conv, member)


@router.post("/{conversation_id}/read")
async def mark_conversation_read(
  conversation_id: str,
  claims: TokenClaims = RequireChat,
  session: AsyncSession = Depends(get_db_session),
):
  member = await repo.mark_conversation_read(
    session,
    organization_id=claims.org,
    conversation_id=conversation_id,
    user_id=claims.sub,
  )
  if member is None:
    raise HTTPException(status_code=404, detail="not a member")
  await session.commit()
  return {"conversation_id": conversation_id, "read": True}


@router.get("/{conversation_id}/membership")
async def my_membership(
  conversation_id: str, claims: TokenClaims = RequireChat, session: AsyncSession = Depends(get_db_session)
):
  q = await session.execute(
    select(ConversationMember).where(
      ConversationMember.organization_id == claims.org,
      ConversationMember.conversation_id == conversation_id,
      ConversationMember.user_id == claims.sub,
    )
  )
  member = q.scalar_one_or_none()
  if member is None:
    raise HTTPException(status_code=404, detail="not a member")
  return {"conversation_id": conversation_id, "user_id": claims.sub, "role": member.role}
