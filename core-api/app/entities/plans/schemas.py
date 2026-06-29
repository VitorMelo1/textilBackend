from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class PlanOut(BaseModel):
  id: str
  key: str
  name: str


class SubscriptionOut(BaseModel):
  id: str
  organization_id: str
  plan_key: str | None = None
  plan_id: str
  status: str
  trial_ends_at: datetime | None = None


class UpdateSubscriptionRequest(BaseModel):
  plan_key: str = Field(pattern="^(basic|professional|enterprise)$")
  trial_days: int | None = Field(default=None, ge=0, le=30)


class BillingCheckoutRequest(BaseModel):
  plan_key: str = Field(pattern="^(basic|professional|enterprise)$")
  success_url: str
  cancel_url: str
  trial_days: int | None = Field(default=None, ge=0, le=30)


class BillingCheckoutResponse(BaseModel):
  checkout_url: str


class BillingPortalRequest(BaseModel):
  return_url: str


class BillingPortalResponse(BaseModel):
  portal_url: str
