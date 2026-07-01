from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import get_settings
from shared.db.models import ConversationMember, Message, OrganizationMember
from shared.db.session import get_db_session, SESSIONMAKER
from shared.events.redis_client import get_redis
from shared.security.jwt import TokenClaims, require_claims
from shared.security.permissions import has_permission


router = APIRouter(tags=["chat"])


def _channel(conversation_id: str) -> str:
  return f"conversation:{conversation_id}"


async def _is_member(session: AsyncSession, *, organization_id: str, conversation_id: str, user_id: str) -> bool:
  q = await session.execute(
    select(ConversationMember.id).where(
      ConversationMember.organization_id == organization_id,
      ConversationMember.conversation_id == conversation_id,
      ConversationMember.user_id == user_id,
    )
  )
  return q.first() is not None


async def _member_can_chat(session: AsyncSession, *, organization_id: str, user_id: str) -> bool:
  """Matriz de permissões (docs/17): slug "chat" cobre mensagens e websocket."""
  q = await session.execute(
    select(OrganizationMember).where(
      OrganizationMember.organization_id == organization_id,
      OrganizationMember.user_id == user_id,
    )
  )
  member = q.scalar_one_or_none()
  if member is None or member.member_status != "active":
    return False
  return has_permission(role=member.role, permissions_csv=member.permissions_csv, slug="chat")


def _claims_from_request_auth(cookie_token: str | None) -> TokenClaims:
  if not cookie_token:
    raise HTTPException(status_code=401, detail="missing auth token")
  try:
    return require_claims(cookie_token)
  except ValueError:
    raise HTTPException(status_code=401, detail="invalid token")


@router.get("/conversations/{conversation_id}/messages")
async def backfill_messages(
  conversation_id: str,
  request: Request,
  after: str | None = Query(default=None, description="ISO datetime (UTC) to fetch after"),
  limit: int = Query(default=50, ge=1, le=200),
  session: AsyncSession = Depends(get_db_session),
):
  settings = get_settings()
  claims = _claims_from_request_auth(request.cookies.get(settings.ACCESS_COOKIE_NAME))
  if not await _member_can_chat(session, organization_id=claims.org, user_id=claims.sub):
    raise HTTPException(status_code=403, detail="chat permission required")
  if not await _is_member(session, organization_id=claims.org, conversation_id=conversation_id, user_id=claims.sub):
    raise HTTPException(status_code=403, detail="not a member")

  q = select(Message).where(Message.conversation_id == conversation_id)
  if after:
    try:
      dt = datetime.fromisoformat(after.replace("Z", "+00:00"))
    except ValueError:
      raise HTTPException(status_code=400, detail="invalid after datetime")
    q = q.where(Message.created_at > dt)
  q = q.order_by(Message.created_at.asc()).limit(limit)

  rows = (await session.execute(q)).scalars().all()
  return [
    {
      "id": m.id,
      "conversation_id": m.conversation_id,
      "sender_user_id": m.sender_user_id,
      "body": m.body,
      "attachment_url": m.attachment_url,
      "attachment_name": m.attachment_name,
      "attachment_content_type": m.attachment_content_type,
      "created_at": m.created_at.isoformat(),
    }
    for m in rows
  ]


@router.websocket("/ws")
async def websocket_chat(ws: WebSocket):
  settings = get_settings()
  token = ws.cookies.get(settings.ACCESS_COOKIE_NAME)
  if not token:
    await ws.close(code=4401)
    return

  try:
    claims = require_claims(token)
  except ValueError:
    await ws.close(code=4401)
    return

  async with SESSIONMAKER() as session:
    allowed = await _member_can_chat(session, organization_id=claims.org, user_id=claims.sub)
  if not allowed:
    await ws.close(code=4403)
    return

  await ws.accept()

  redis = get_redis()
  pubsub = redis.pubsub()
  subscribed: set[str] = set()

  async def reader_task():
    try:
      async for msg in pubsub.listen():
        if msg.get("type") != "message":
          continue
        data = msg.get("data")
        if not data:
          continue
        try:
          payload = json.loads(data)
        except Exception:
          continue
        await ws.send_json({"type": "message", "payload": payload})
    except Exception:
      # websocket likely closed
      return

  reader: asyncio.Task | None = None

  def _ensure_reader() -> None:
    # redis-py: pubsub.listen() encerra imediatamente se não houver assinatura
    # ativa; o reader só pode iniciar depois do primeiro subscribe.
    nonlocal reader
    if reader is None or reader.done():
      reader = asyncio.create_task(reader_task())

  try:
    while True:
      incoming = await ws.receive_json()
      mtype = incoming.get("type")

      if mtype == "join":
        conversation_id = str(incoming.get("conversation_id") or "")
        if not conversation_id:
          await ws.send_json({"type": "error", "message": "conversation_id required"})
          continue
        async with SESSIONMAKER() as session:
          ok = await _is_member(
            session, organization_id=claims.org, conversation_id=conversation_id, user_id=claims.sub
          )
        if not ok:
          await ws.send_json({"type": "error", "message": "not a member"})
          continue
        if conversation_id not in subscribed:
          await pubsub.subscribe(_channel(conversation_id))
          subscribed.add(conversation_id)
        _ensure_reader()
        await ws.send_json({"type": "joined", "conversation_id": conversation_id})

      elif mtype == "message":
        conversation_id = str(incoming.get("conversation_id") or "")
        body = str(incoming.get("body") or "").strip()
        attachment = incoming.get("attachment") if isinstance(incoming.get("attachment"), dict) else {}
        attachment_url = str(attachment.get("url") or "").strip() or None
        attachment_name = str(attachment.get("name") or "").strip() or None
        attachment_content_type = str(attachment.get("content_type") or "").strip() or None
        if not conversation_id or (not body and not attachment_url):
          await ws.send_json({"type": "error", "message": "conversation_id and body required"})
          continue

        async with SESSIONMAKER() as session:
          ok = await _is_member(
            session, organization_id=claims.org, conversation_id=conversation_id, user_id=claims.sub
          )
          if not ok:
            await ws.send_json({"type": "error", "message": "not a member"})
            continue
          msg_row = Message(
            organization_id=claims.org,
            conversation_id=conversation_id,
            sender_user_id=claims.sub,
            body=body,
            attachment_url=attachment_url,
            attachment_name=attachment_name,
            attachment_content_type=attachment_content_type,
          )
          session.add(msg_row)
          await session.flush()
          await session.commit()

          payload = {
            "id": msg_row.id,
            "conversation_id": conversation_id,
            "sender_user_id": claims.sub,
            "body": body,
            "attachment_url": attachment_url,
            "attachment_name": attachment_name,
            "attachment_content_type": attachment_content_type,
            "created_at": msg_row.created_at.replace(tzinfo=timezone.utc).isoformat(),
          }
          await redis.publish(_channel(conversation_id), json.dumps(payload, ensure_ascii=False))
          await ws.send_json({"type": "ack", "message_id": msg_row.id})

      else:
        await ws.send_json({"type": "error", "message": "unknown type"})

  except WebSocketDisconnect:
    pass
  finally:
    try:
      if reader is not None:
        reader.cancel()
    except Exception:
      pass
    try:
      await pubsub.close()
    except Exception:
      pass
    try:
      await ws.close()
    except Exception:
      pass
