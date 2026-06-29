from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


INTEREST_REQUEST_STATUSES = ("pending", "matched", "rejected")


class InterestRequestCreate(BaseModel):
  provider_id: str
  message: str | None = None
  target_city: str | None = Field(default=None, max_length=240)
  target_state: str | None = Field(default=None, max_length=2)


class InterestRequestUpdate(BaseModel):
  status: Literal["matched", "rejected"]


class InterestRequestOut(BaseModel):
  id: str
  organization_id: str
  provider_id: str
  requester_user_id: str
  message: str | None = None
  target_city: str | None = None
  target_state: str | None = None
  status: str
  created_at: datetime
  updated_at: datetime
