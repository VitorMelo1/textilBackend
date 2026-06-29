from __future__ import annotations

from pydantic import BaseModel


class TokenPair(BaseModel):
  access_token: str
  refresh_token: str
  token_type: str = "bearer"


class RegisterRequest(BaseModel):
  email: str
  name: str
  password: str
  organization_name: str | None = None
  user_type: str | None = None
  business_profile: str | None = None


class LoginRequest(BaseModel):
  email: str
  password: str


class RefreshRequest(BaseModel):
  refresh_token: str | None = None


class MeResponse(BaseModel):
  user_id: str
  organization_id: str
  email: str | None = None
  name: str | None = None
  company_name: str | None = None  # Organization.name
  phone: str | None = None  # Organization.phone
  description: str | None = None  # Organization.description
  user_type: str | None = None
  business_profile: str | None = None
  plan_key: str | None = None
  role: str | None = None


class UpdateMeRequest(BaseModel):
  name: str | None = None
  company_name: str | None = None
  phone: str | None = None
  description: str | None = None


class ChangePasswordRequest(BaseModel):
  current_password: str
  new_password: str
