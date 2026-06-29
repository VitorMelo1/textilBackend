from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


PermissionSlug = Literal["pedidos", "estoque", "custos", "fichas", "rede", "chat", "relatorios", "configuracoes"]


class MemberOut(BaseModel):
  id: str
  user_id: str
  email: str
  name: str
  role: str
  job_title: str | None = None
  member_status: str
  permissions: list[str]
  last_active_at: datetime | None = None
  created_at: datetime


class MemberUpdate(BaseModel):
  role: Literal["owner", "member"] | None = None
  job_title: str | None = Field(default=None, max_length=120)
  member_status: Literal["active", "pending", "inactive"] | None = None
  permissions: list[PermissionSlug] | None = None


class InviteCreate(BaseModel):
  email: str
  job_title: str | None = Field(default=None, max_length=120)
  permissions: list[PermissionSlug] = []


class InviteOut(BaseModel):
  id: str
  organization_id: str
  email: str
  job_title: str | None = None
  permissions: list[str]
  invited_by_user_id: str
  status: str
  expires_at: datetime
  accepted_at: datetime | None = None
  acceptance_token: str | None = None
  created_at: datetime


class InviteAcceptRequest(BaseModel):
  token: str
