from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import Conversation, ConversationMember, InterestRequest, Message, Order, OrganizationMember, Provider


async def get_provider(session: AsyncSession, provider_id: str) -> Provider | None:
  q = await session.execute(select(Provider).where(Provider.id == provider_id))
  return q.scalar_one_or_none()


async def get_provider_conversation(
  session: AsyncSession,
  *,
  organization_id: str,
  provider_id: str,
) -> Conversation | None:
  q = await session.execute(
    select(Conversation).where(
      Conversation.organization_id == organization_id,
      Conversation.provider_id == provider_id,
    )
  )
  return q.scalar_one_or_none()


async def get_interest_request(session: AsyncSession, interest_request_id: str) -> InterestRequest | None:
  q = await session.execute(select(InterestRequest).where(InterestRequest.id == interest_request_id))
  return q.scalar_one_or_none()


async def get_order(session: AsyncSession, order_id: str) -> Order | None:
  q = await session.execute(select(Order).where(Order.id == order_id))
  return q.scalar_one_or_none()


async def get_interest_conversation(
  session: AsyncSession,
  *,
  organization_id: str,
  interest_request_id: str,
) -> Conversation | None:
  q = await session.execute(
    select(Conversation).where(
      Conversation.organization_id == organization_id,
      Conversation.interest_request_id == interest_request_id,
    )
  )
  return q.scalar_one_or_none()


async def get_order_conversation(
  session: AsyncSession,
  *,
  organization_id: str,
  order_id: str,
) -> Conversation | None:
  q = await session.execute(
    select(Conversation).where(
      Conversation.organization_id == organization_id,
      Conversation.order_id == order_id,
    )
  )
  return q.scalar_one_or_none()


async def list_active_chat_member_user_ids(session: AsyncSession, *, organization_id: str) -> list[str]:
  q = await session.execute(
    select(OrganizationMember.user_id)
    .where(
      OrganizationMember.organization_id == organization_id,
      OrganizationMember.member_status == "active",
    )
    .order_by(OrganizationMember.role.desc(), OrganizationMember.created_at.asc())
  )
  return [row[0] for row in q]


async def create_provider_conversation(
  session: AsyncSession,
  *,
  organization_id: str,
  provider_id: str,
  title: str,
  members: list[tuple[str, str]],
  interest_request_id: str | None = None,
  order_id: str | None = None,
) -> Conversation:
  conversation = Conversation(
    organization_id=organization_id,
    provider_id=provider_id,
    interest_request_id=interest_request_id,
    order_id=order_id,
    title=title,
  )
  session.add(conversation)
  await session.flush()

  seen: set[str] = set()
  for member_organization_id, user_id in members:
    if user_id in seen:
      continue
    seen.add(user_id)
    session.add(
      ConversationMember(
        organization_id=member_organization_id,
        conversation_id=conversation.id,
        user_id=user_id,
        role="member",
      )
    )
  await session.flush()
  return conversation


async def create_order_conversation(
  session: AsyncSession,
  *,
  organization_id: str,
  order_id: str,
  title: str,
  members: list[str],
) -> Conversation:
  conversation = Conversation(organization_id=organization_id, order_id=order_id, title=title)
  session.add(conversation)
  await session.flush()
  for user_id in dict.fromkeys(members):
    session.add(
      ConversationMember(
        organization_id=organization_id,
        conversation_id=conversation.id,
        user_id=user_id,
        role="member",
      )
    )
  await session.flush()
  return conversation


async def get_my_membership(
  session: AsyncSession,
  *,
  organization_id: str,
  conversation_id: str,
  user_id: str,
) -> ConversationMember | None:
  q = await session.execute(
    select(ConversationMember).where(
      ConversationMember.organization_id == organization_id,
      ConversationMember.conversation_id == conversation_id,
      ConversationMember.user_id == user_id,
    )
  )
  return q.scalar_one_or_none()


async def mark_conversation_read(
  session: AsyncSession,
  *,
  organization_id: str,
  conversation_id: str,
  user_id: str,
) -> ConversationMember | None:
  member = await get_my_membership(
    session,
    organization_id=organization_id,
    conversation_id=conversation_id,
    user_id=user_id,
  )
  if member is None:
    return None
  member.last_read_at = datetime.now(timezone.utc)
  await session.flush()
  return member


async def get_conversation_meta(
  session: AsyncSession,
  *,
  conversation_id: str,
  member: ConversationMember,
) -> tuple[int, Message | None]:
  conditions = [
    Message.conversation_id == conversation_id,
    Message.sender_user_id != member.user_id,
  ]
  if member.last_read_at is not None:
    conditions.append(Message.created_at > member.last_read_at)
  unread_q = await session.execute(
    select(func.count(Message.id)).where(*conditions)
  )
  last_q = await session.execute(
    select(Message)
    .where(Message.conversation_id == conversation_id)
    .order_by(Message.created_at.desc())
    .limit(1)
  )
  return int(unread_q.scalar_one() or 0), last_q.scalar_one_or_none()
