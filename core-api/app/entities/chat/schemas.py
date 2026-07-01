from __future__ import annotations

from pydantic import BaseModel


class ConversationCreate(BaseModel):
  title: str | None = None
  member_user_ids: list[str] = []


class ConversationOut(BaseModel):
  id: str
  organization_id: str
  title: str | None = None
  provider_id: str | None = None
  interest_request_id: str | None = None
  order_id: str | None = None
  unread_count: int = 0
  last_message_body: str | None = None
  last_message_at: str | None = None
