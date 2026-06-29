from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.entities.team import service
from app.entities.team.schemas import InviteCreate, MemberUpdate


def test_permissions_to_csv() -> None:
  assert service.permissions_to_csv(["rede", "pedidos", "rede"]) == "pedidos,rede"


def test_invite_delivery_out_exposes_token_when_email_delivery_is_disabled() -> None:
  invite = service.InviteOut(
    id="i1",
    organization_id="org-1",
    email="x@x.com",
    permissions=["rede"],
    invited_by_user_id="u1",
    status="pending",
    expires_at=datetime.now(timezone.utc).replace(year=2099),
    created_at=datetime.now(timezone.utc),
  )

  out = service.invite_delivery_out(invite, raw_token="raw-token", email_delivery_enabled=False)

  assert out.acceptance_token == "raw-token"


def test_invite_delivery_out_hides_token_when_email_delivery_is_enabled() -> None:
  invite = service.InviteOut(
    id="i1",
    organization_id="org-1",
    email="x@x.com",
    permissions=["rede"],
    invited_by_user_id="u1",
    status="pending",
    expires_at=datetime.now(timezone.utc).replace(year=2099),
    created_at=datetime.now(timezone.utc),
  )

  out = service.invite_delivery_out(invite, raw_token="raw-token", email_delivery_enabled=True)

  assert out.acceptance_token is None


@pytest.mark.asyncio
async def test_update_member_rejects_last_owner_demotion() -> None:
  session = AsyncMock()
  member = type("Member", (), {"id": "m1", "organization_id": "org-1", "role": "owner"})()
  with (
    patch("app.entities.team.service.repo.get_member_by_id", new=AsyncMock(return_value=member)),
    patch("app.entities.team.service.repo.count_owners", new=AsyncMock(return_value=1)),
  ):
    with pytest.raises(HTTPException) as exc:
      await service.update_member(
        session,
        organization_id="org-1",
        member_id="m1",
        body=MemberUpdate(role="member"),
      )
  assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_accept_invite_requires_pending_status() -> None:
  session = AsyncMock()
  invite = type(
    "Invite",
    (),
    {
      "id": "i1",
      "organization_id": "org-1",
      "status": "revoked",
      "expires_at": datetime.now(timezone.utc).replace(year=2099),
      "token_hash": "hash",
    },
  )()
  with patch("app.entities.team.service.repo.get_invite_by_id", new=AsyncMock(return_value=invite)):
    with pytest.raises(HTTPException) as exc:
      await service.accept_invite(
        session,
        invite_id="i1",
        token="raw-token",
        current_user_id="user-1",
      )
  assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_create_invite_default_pending() -> None:
  session = AsyncMock()
  invite_row = type(
    "Invite",
    (),
    {
      "id": "i1",
      "organization_id": "org-1",
      "email": "x@x.com",
      "job_title": None,
      "permissions_csv": "rede",
      "invited_by_user_id": "u1",
      "status": "pending",
      "expires_at": datetime.now(timezone.utc).replace(year=2099),
      "accepted_at": None,
      "created_at": datetime.now(timezone.utc),
    },
  )()
  with (
    patch("app.entities.team.service.new_token_urlsafe", return_value="raw"),
    patch("app.entities.team.service.sha256_hex", return_value="hash"),
    patch("app.entities.team.service.repo.create_invite", new=AsyncMock(return_value=invite_row)),
  ):
    invite, raw = await service.create_invite(
      session,
      organization_id="org-1",
      invited_by_user_id="u1",
      body=InviteCreate(email="x@x.com", permissions=["rede"]),
    )
  assert raw == "raw"
  assert invite.status == "pending"
