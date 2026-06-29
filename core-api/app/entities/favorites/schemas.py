from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ProviderFavoriteCreate(BaseModel):
  provider_id: str


class ProviderFavoriteOut(BaseModel):
  id: str
  organization_id: str
  provider_id: str
  user_id: str
  provider_name: str
  provider_type: str
  location: str | None = None
  rating: float
  review_count: int
  verified: bool
  added_date: datetime
  last_contact_at: datetime | None = None
