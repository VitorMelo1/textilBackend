from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from ..config import get_settings


@dataclass(frozen=True)
class TokenClaims:
  sub: str
  org: str
  role: str | None = None


def _now() -> datetime:
  return datetime.now(timezone.utc)


def create_access_token(*, subject: str, organization_id: str, role: str | None = None) -> str:
  s = get_settings()
  exp = _now() + timedelta(seconds=s.ACCESS_TOKEN_TTL_SECONDS)
  payload: dict[str, Any] = {
    "iss": s.JWT_ISSUER,
    "aud": s.JWT_AUDIENCE,
    "iat": int(_now().timestamp()),
    "exp": int(exp.timestamp()),
    "sub": subject,
    "org": organization_id,
  }
  if role:
    payload["role"] = role
  return jwt.encode(payload, s.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any]:
  s = get_settings()
  return jwt.decode(token, s.JWT_SECRET, algorithms=["HS256"], audience=s.JWT_AUDIENCE, issuer=s.JWT_ISSUER)


def require_claims(token: str) -> TokenClaims:
  try:
    payload = decode_token(token)
    sub = str(payload["sub"])
    org = str(payload["org"])
    role = payload.get("role")
    return TokenClaims(sub=sub, org=org, role=str(role) if role is not None else None)
  except (JWTError, KeyError) as e:
    raise ValueError("Invalid token") from e
