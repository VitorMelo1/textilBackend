from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.api.pagination import PaginatedResponse, PaginationParams, pagination_params
from shared.config import get_settings
from shared.db.session import get_db_session
from shared.security.deps import require_auth_claims
from shared.security.jwt import TokenClaims
from shared.security.permissions import require_owner

from . import service
from .schemas import InviteAcceptRequest, InviteCreate, InviteOut, MemberOut, MemberUpdate


router = APIRouter(prefix="/organization", tags=["team"])

RequireOwner = Depends(require_owner())


@router.get("/members", response_model=PaginatedResponse[MemberOut])
async def list_members(
  claims: TokenClaims = RequireOwner,
  session: AsyncSession = Depends(get_db_session),
  pagination: PaginationParams = Depends(pagination_params),
):
  return await service.list_members(session, organization_id=claims.org, pagination=pagination)


@router.patch("/members/{member_id}", response_model=MemberOut)
async def update_member(
  member_id: str,
  body: MemberUpdate,
  claims: TokenClaims = RequireOwner,
  session: AsyncSession = Depends(get_db_session),
):
  result = await service.update_member(
    session,
    organization_id=claims.org,
    member_id=member_id,
    body=body,
  )
  await session.commit()
  return result


@router.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_member(
  member_id: str,
  claims: TokenClaims = RequireOwner,
  session: AsyncSession = Depends(get_db_session),
):
  await service.delete_member(session, organization_id=claims.org, member_id=member_id)
  await session.commit()


@router.post("/invites", response_model=InviteOut, status_code=status.HTTP_201_CREATED)
async def create_invite(
  body: InviteCreate,
  claims: TokenClaims = RequireOwner,
  session: AsyncSession = Depends(get_db_session),
):
  invite, raw_token = await service.create_invite(
    session,
    organization_id=claims.org,
    invited_by_user_id=claims.sub,
    body=body,
  )
  await session.commit()
  settings = get_settings()
  return service.invite_delivery_out(
    invite,
    raw_token=raw_token,
    email_delivery_enabled=settings.INVITE_EMAIL_DELIVERY_ENABLED,
  )


@router.get("/invites", response_model=PaginatedResponse[InviteOut])
async def list_invites(
  claims: TokenClaims = RequireOwner,
  session: AsyncSession = Depends(get_db_session),
  pagination: PaginationParams = Depends(pagination_params),
  status_filter: str | None = Query(default="pending", alias="status"),
):
  return await service.list_invites(
    session,
    organization_id=claims.org,
    pagination=pagination,
    status_filter=status_filter,
  )


@router.post("/invites/{invite_id}/accept")
async def accept_invite(
  invite_id: str,
  body: InviteAcceptRequest,
  claims: TokenClaims = Depends(require_auth_claims),
  session: AsyncSession = Depends(get_db_session),
):
  result = await service.accept_invite(
    session,
    invite_id=invite_id,
    token=body.token,
    current_user_id=claims.sub,
  )
  await session.commit()
  return result


@router.post("/invites/{invite_id}/cancel")
async def cancel_invite(
  invite_id: str,
  claims: TokenClaims = RequireOwner,
  session: AsyncSession = Depends(get_db_session),
):
  result = await service.cancel_invite(
    session,
    organization_id=claims.org,
    invite_id=invite_id,
  )
  await session.commit()
  return result
