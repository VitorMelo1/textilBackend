from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.entities.identity.service import rotate_refresh_token


@pytest.mark.asyncio
async def test_rotate_refresh_token_preserves_role() -> None:
  rt = type(
    "RT",
    (),
    {
      "user_id": "user-1",
      "organization_id": "org-1",
      "revoked_at": None,
      "expires_at": datetime.now(timezone.utc).replace(year=2099),
    },
  )()
  member = type("Member", (), {"role": "owner", "member_status": "active"})()
  session = AsyncMock()

  with (
    patch("app.entities.identity.service.repo.get_refresh_token_record", new=AsyncMock(return_value=rt)),
    patch("app.entities.identity.service.repo.revoke_refresh_token", new=AsyncMock(return_value=True)),
    patch("app.entities.identity.service.repo.get_org_membership", new=AsyncMock(return_value=member)),
    patch(
      "app.entities.identity.service.issue_tokens_for_user",
      new=AsyncMock(return_value=("access-token", "refresh-token")),
    ) as issue_mock,
  ):
    result = await rotate_refresh_token(session, raw_refresh_token="raw")

  assert result == ("access-token", "refresh-token")
  issue_mock.assert_awaited_once_with(session, user_id="user-1", organization_id="org-1", role="owner")


@pytest.mark.asyncio
async def test_rotate_refresh_token_rejects_inactive_member() -> None:
  rt = type(
    "RT",
    (),
    {
      "user_id": "user-1",
      "organization_id": "org-1",
      "revoked_at": None,
      "expires_at": datetime.now(timezone.utc).replace(year=2099),
    },
  )()
  member = type("Member", (), {"role": "member", "member_status": "inactive"})()
  session = AsyncMock()

  with (
    patch("app.entities.identity.service.repo.get_refresh_token_record", new=AsyncMock(return_value=rt)),
    patch("app.entities.identity.service.repo.revoke_refresh_token", new=AsyncMock(return_value=True)),
    patch("app.entities.identity.service.repo.get_org_membership", new=AsyncMock(return_value=member)),
  ):
    result = await rotate_refresh_token(session, raw_refresh_token="raw")

  assert result is None
