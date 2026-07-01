from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from authlib.integrations.starlette_client import OAuth, OAuthError
from starlette.requests import Request
from starlette.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import get_settings
from shared.db.session import get_db_session
from shared.security.deps import require_auth_claims

from .schemas import (
  ChangePasswordRequest,
  LoginRequest,
  MeResponse,
  RefreshRequest,
  RegisterRequest,
  TokenPair,
  UpdateMeRequest,
)
from .service import issue_tokens_for_user, rotate_refresh_token
from . import repo as identity_repo
from .repo import (
  create_local_user_with_org,
  get_user_by_email,
  update_user_and_org,
  upsert_oauth_login,
)
from shared.security.hashing import sha256_hex
from shared.security.passwords import hash_password, verify_password
from shared.security.rate_limit import enforce_rate_limit
from app.entities.network.service import upsert_provider_profile_for_org


router = APIRouter(prefix="/auth", tags=["auth"])

LOGIN_IP_MAX_ATTEMPTS = 30
LOGIN_CREDENTIAL_MAX_ATTEMPTS = 10
LOGIN_WINDOW_SECONDS = 300


def _set_auth_cookies(response: Response, access: str, refresh: str) -> None:
  settings = get_settings()
  response.set_cookie(
    key=settings.ACCESS_COOKIE_NAME,
    value=access,
    httponly=True,
    secure=settings.AUTH_COOKIE_SECURE,
    samesite=settings.AUTH_COOKIE_SAMESITE,
    domain=settings.AUTH_COOKIE_DOMAIN,
    max_age=settings.ACCESS_TOKEN_TTL_SECONDS,
    path="/",
  )
  response.set_cookie(
    key=settings.REFRESH_COOKIE_NAME,
    value=refresh,
    httponly=True,
    secure=settings.AUTH_COOKIE_SECURE,
    samesite=settings.AUTH_COOKIE_SAMESITE,
    domain=settings.AUTH_COOKIE_DOMAIN,
    max_age=settings.REFRESH_TOKEN_TTL_DAYS * 24 * 60 * 60,
    path="/",
  )


def _clear_auth_cookies(response: Response) -> None:
  settings = get_settings()
  response.delete_cookie(key=settings.ACCESS_COOKIE_NAME, path="/", domain=settings.AUTH_COOKIE_DOMAIN)
  response.delete_cookie(key=settings.REFRESH_COOKIE_NAME, path="/", domain=settings.AUTH_COOKIE_DOMAIN)


def _oauth() -> OAuth:
  settings = get_settings()
  oauth = OAuth()
  if settings.OAUTH_GOOGLE_CLIENT_ID and settings.OAUTH_GOOGLE_CLIENT_SECRET:
    oauth.register(
      name="google",
      client_id=settings.OAUTH_GOOGLE_CLIENT_ID,
      client_secret=settings.OAUTH_GOOGLE_CLIENT_SECRET,
      server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
      client_kwargs={"scope": "openid email profile"},
    )
  return oauth


@router.get("/oauth/google/start")
async def oauth_google_start(request: Request):
  settings = get_settings()
  oauth = _oauth()
  if "google" not in oauth:
    raise HTTPException(
      status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
      detail="OAuth google not configured. Set OAUTH_GOOGLE_CLIENT_ID/SECRET.",
    )

  redirect_uri = settings.OAUTH_GOOGLE_REDIRECT_URI or str(request.url_for("oauth_google_callback"))
  return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/oauth/google/callback", name="oauth_google_callback")
async def oauth_google_callback(
  request: Request,
  response: Response,
  session: AsyncSession = Depends(get_db_session),
):
  oauth = _oauth()
  try:
    token = await oauth.google.authorize_access_token(request)
  except OAuthError as e:
    raise HTTPException(status_code=400, detail=f"OAuth error: {e.error}") from e

  userinfo = token.get("userinfo")
  if not userinfo:
    # fallback via userinfo endpoint
    userinfo = await oauth.google.userinfo(token=token)

  email = str(userinfo.get("email") or "")
  name = str(userinfo.get("name") or userinfo.get("given_name") or "Usuário")
  sub = str(userinfo.get("sub") or "")
  if not email or not sub:
    raise HTTPException(status_code=400, detail="OAuth: missing email/sub in userinfo")

  user, member = await upsert_oauth_login(
    session,
    provider="google",
    provider_account_id=sub,
    email=email,
    name=name,
    token_data=token,
  )
  org = await identity_repo.get_org_by_id(session, member.organization_id)
  await upsert_provider_profile_for_org(
    session,
    organization_id=member.organization_id,
    owner_user_id=user.id,
    name=(org.name if org else user.name),
    business_profile=user.business_profile,
    user_type=user.user_type,
    description=(org.description if org else None),
  )

  access, refresh = await issue_tokens_for_user(
    session, user_id=user.id, organization_id=member.organization_id, role=member.role
  )
  await session.commit()
  _set_auth_cookies(response, access, refresh)

  settings = get_settings()
  if settings.FRONTEND_OAUTH_REDIRECT:
    return RedirectResponse(url=settings.FRONTEND_OAUTH_REDIRECT, status_code=302)
  # Dev fallback: return JSON so frontend can read tokens directly
  return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenPair)
async def refresh_tokens(
  response: Response,
  request: Request,
  payload: RefreshRequest | None = None,
  session: AsyncSession = Depends(get_db_session),
):
  settings = get_settings()
  refresh_cookie = request.cookies.get(settings.REFRESH_COOKIE_NAME)
  raw = str((payload.refresh_token if payload else None) or refresh_cookie or "")
  if not raw:
    raise HTTPException(status_code=400, detail="refresh_token required")
  rotated = await rotate_refresh_token(session, raw_refresh_token=raw)
  if rotated is None:
    raise HTTPException(status_code=401, detail="invalid refresh token")
  access, refresh = rotated
  await session.commit()
  _set_auth_cookies(response, access, refresh)
  return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/register", response_model=TokenPair)
async def register_local(
  body: RegisterRequest,
  response: Response,
  session: AsyncSession = Depends(get_db_session),
):
  existing = await get_user_by_email(session, body.email.lower().strip())
  if existing is not None:
    raise HTTPException(status_code=409, detail="email already registered")

  user, member = await create_local_user_with_org(
    session,
    email=body.email.lower().strip(),
    name=body.name.strip(),
    password=body.password,
    organization_name=(body.organization_name.strip() if body.organization_name else None),
    user_type=body.user_type,
    business_profile=body.business_profile,
  )
  await upsert_provider_profile_for_org(
    session,
    organization_id=member.organization_id,
    owner_user_id=user.id,
    name=(body.organization_name.strip() if body.organization_name else body.name.strip()),
    business_profile=body.business_profile,
    user_type=body.user_type,
  )
  access, refresh = await issue_tokens_for_user(
    session, user_id=user.id, organization_id=member.organization_id, role=member.role
  )
  await session.commit()
  _set_auth_cookies(response, access, refresh)
  return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/login", response_model=TokenPair)
async def login_local(
  body: LoginRequest,
  request: Request,
  response: Response,
  session: AsyncSession = Depends(get_db_session),
):
  email = body.email.lower().strip()
  client_ip = request.client.host if request.client else "unknown"
  # Conta toda tentativa (válida ou não) para conter brute force e enumeração.
  await enforce_rate_limit(
    key=f"auth:login:ip:{client_ip}",
    max_attempts=LOGIN_IP_MAX_ATTEMPTS,
    window_seconds=LOGIN_WINDOW_SECONDS,
  )
  await enforce_rate_limit(
    key=f"auth:login:cred:{client_ip}:{sha256_hex(email)[:16]}",
    max_attempts=LOGIN_CREDENTIAL_MAX_ATTEMPTS,
    window_seconds=LOGIN_WINDOW_SECONDS,
  )

  user = await get_user_by_email(session, email)
  if user is None or not user.password_hash:
    raise HTTPException(status_code=401, detail="invalid credentials")
  if not verify_password(body.password, user.password_hash):
    raise HTTPException(status_code=401, detail="invalid credentials")

  member = await identity_repo.get_first_org_for_user(session, user.id)
  if member is None:
    raise HTTPException(status_code=400, detail="user has no organization")
  org = await identity_repo.get_org_by_id(session, member.organization_id)
  await upsert_provider_profile_for_org(
    session,
    organization_id=member.organization_id,
    owner_user_id=user.id,
    name=(org.name if org else user.name),
    business_profile=user.business_profile,
    user_type=user.user_type,
    description=(org.description if org else None),
  )
  access, refresh = await issue_tokens_for_user(
    session, user_id=user.id, organization_id=member.organization_id, role=member.role
  )
  await session.commit()
  _set_auth_cookies(response, access, refresh)
  return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
  _clear_auth_cookies(response)


@router.get("/me", response_model=MeResponse)
async def me(claims=Depends(require_auth_claims), session: AsyncSession = Depends(get_db_session)):
  user = await identity_repo.get_user_by_id(session, claims.sub)
  org = await identity_repo.get_org_by_id(session, claims.org)
  plan_key = await identity_repo.get_subscription_plan_key(session, claims.org)
  return MeResponse(
    user_id=claims.sub,
    organization_id=claims.org,
    email=(user.email if user else None),
    name=(user.name if user else None),
    company_name=(org.name if org else None),
    phone=(org.phone if org else None),
    description=(org.description if org else None),
    user_type=(user.user_type if user else None),
    business_profile=(user.business_profile if user else None),
    plan_key=plan_key,
    role=claims.role,
  )


@router.patch("/me", response_model=MeResponse)
async def update_me(
  body: UpdateMeRequest,
  claims=Depends(require_auth_claims),
  session: AsyncSession = Depends(get_db_session),
):
  result = await update_user_and_org(
    session,
    user_id=claims.sub,
    org_id=claims.org,
    name=body.name,
    company_name=body.company_name,
    phone=body.phone,
    description=body.description,
  )
  if result is None:
    raise HTTPException(status_code=404, detail="user or organization not found")
  user, org = result
  await upsert_provider_profile_for_org(
    session,
    organization_id=claims.org,
    owner_user_id=claims.sub,
    name=org.name,
    business_profile=user.business_profile,
    user_type=user.user_type,
    description=org.description,
  )
  plan_key = await identity_repo.get_subscription_plan_key(session, claims.org)
  await session.commit()
  return MeResponse(
    user_id=claims.sub,
    organization_id=claims.org,
    email=user.email,
    name=user.name,
    company_name=(org.name if org else None),
    phone=(org.phone if org else None),
    description=(org.description if org else None),
    user_type=user.user_type,
    business_profile=user.business_profile,
    plan_key=plan_key,
    role=claims.role,
  )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
  body: ChangePasswordRequest,
  claims=Depends(require_auth_claims),
  session: AsyncSession = Depends(get_db_session),
):
  user = await identity_repo.get_user_by_id(session, claims.sub)
  if user is None or not user.password_hash:
    raise HTTPException(status_code=400, detail="cannot change password for this account")
  if not verify_password(body.current_password, user.password_hash):
    raise HTTPException(status_code=400, detail="current password is incorrect")
  if len(body.new_password) < 8:
    raise HTTPException(status_code=422, detail="new password must be at least 8 characters")
  user.password_hash = hash_password(body.new_password)
  await session.commit()
