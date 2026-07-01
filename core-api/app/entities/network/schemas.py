from __future__ import annotations

from pydantic import BaseModel


class ProviderOut(BaseModel):
  id: str
  name: str
  provider_type: str
  organization_id: str | None = None
  location: str | None = None
  capacity: str | None = None
  verified: bool
  rating: float
  review_count: int
  can_chat: bool = False


class ProviderCreate(BaseModel):
  # "verified" não é aceito do cliente: o selo só é concedido por fluxo administrativo.
  name: str
  provider_type: str
  location: str | None = None
  capacity: str | None = None
  description: str | None = None
