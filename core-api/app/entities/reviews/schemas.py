from __future__ import annotations

from pydantic import BaseModel, Field


class ReviewCreate(BaseModel):
  provider_id: str
  rating: int = Field(ge=1, le=5)
  comment: str | None = None
  quality: int = Field(default=0, ge=0, le=5)
  deadline: int = Field(default=0, ge=0, le=5)
  communication: int = Field(default=0, ge=0, le=5)


class ReviewOut(BaseModel):
  id: str
  organization_id: str
  provider_id: str
  provider_name: str | None = None
  author_user_id: str
  rating: int
  comment: str | None = None
  quality: int
  deadline: int
  communication: int
  created_at: str | None = None
