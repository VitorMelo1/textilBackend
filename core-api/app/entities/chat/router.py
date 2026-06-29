from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import Conversation, ConversationMember
from shared.db.session import get_db_session
from shared.security.jwt import TokenClaims
from shared.security.permissions import require_permission

from .schemas import ConversationCreate, ConversationOut
from .service import find_missing_org_members


router = APIRouter(prefix="/conversations", tags=["chat"])

# Matriz de permissões (docs/17): slug "chat" cobre conversations, messages e websocket.
RequireChat = Depends(require_permission("chat"))


@router.get("", response_model=list[ConversationOut])
async def list_conversations(claims: TokenClaims = RequireChat, session: AsyncSession = Depends(get_db_session)):
  q = await session.execute(
    select(Conversation)
    .join(ConversationMember, ConversationMember.conversation_id == Conversation.id)
    .where(Conversation.organization_id == claims.org, ConversationMember.user_id == claims.sub)
    .order_by(Conversation.created_at.desc())
  )
  rows = q.scalars().all()
  return [ConversationOut(id=c.id, organization_id=c.organization_id, title=c.title) for c in rows]


@router.post("", response_model=ConversationOut)
async def create_conversation(
  body: ConversationCreate,
  claims: TokenClaims = RequireChat,
  session: AsyncSession = Depends(get_db_session),
):
  requested = {uid for uid in body.member_user_ids if uid}
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
  return ConversationOut(id=conv.id, organization_id=conv.organization_id, title=conv.title)


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
