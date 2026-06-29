from __future__ import annotations

from fastapi import Header, HTTPException, Request, status

from shared.config import get_settings
from .jwt import TokenClaims, require_claims


def _extract_bearer(authorization: str | None) -> str | None:
  if not authorization:
    return None
  parts = authorization.split(" ", 1)
  if len(parts) != 2:
    return None
  scheme, token = parts
  if scheme.lower() != "bearer":
    return None
  return token.strip() or None


async def require_auth_claims(
  request: Request,
  authorization: str | None = Header(default=None),
) -> TokenClaims:
  settings = get_settings()
  token = _extract_bearer(authorization)
  if not token:
    token = request.cookies.get(settings.ACCESS_COOKIE_NAME)
  if not token:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing auth token")
  try:
    return require_claims(token)
  except ValueError:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
