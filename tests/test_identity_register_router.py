"""
Testes de integração do endpoint /auth/register.
Requerem asyncpg (driver PostgreSQL) — pulados se não estiver instalado.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("asyncpg")

from fastapi import HTTPException

from app.entities.identity.router import register_local
from app.entities.identity.schemas import RegisterRequest


@pytest.mark.asyncio
async def test_register_endpoint_forwards_business_profile_to_repo() -> None:
  """O endpoint /auth/register repassa user_type e business_profile ao repo."""
  fake_user = type("User", (), {"id": "user-1"})()
  fake_member = type("Member", (), {"organization_id": "org-1", "role": "owner"})()

  body = RegisterRequest(
    email="Test@X.com",
    name="Test User",
    password="secret123",
    business_profile="atelier",
    user_type="faccao",
  )
  session = AsyncMock()
  response = MagicMock()

  with (
    patch(
      "app.entities.identity.router.get_user_by_email",
      new=AsyncMock(return_value=None),
    ),
    patch(
      "app.entities.identity.router.create_local_user_with_org",
      new=AsyncMock(return_value=(fake_user, fake_member)),
    ) as create_mock,
    patch(
      "app.entities.identity.router.issue_tokens_for_user",
      new=AsyncMock(return_value=("access", "refresh")),
    ),
    patch(
      "app.entities.identity.router.upsert_provider_profile_for_org",
      new=AsyncMock(),
    ) as provider_upsert_mock,
    patch("app.entities.identity.router._set_auth_cookies"),
    patch("app.entities.identity.router.get_settings"),
  ):
    result = await register_local(body=body, response=response, session=session)

  create_mock.assert_awaited_once_with(
    session,
    email="test@x.com",
    name="Test User",
    password="secret123",
    organization_name=None,
    user_type="faccao",
    business_profile="atelier",
  )
  provider_upsert_mock.assert_awaited_once_with(
    session,
    organization_id="org-1",
    owner_user_id="user-1",
    name="Test User",
    business_profile="atelier",
    user_type="faccao",
  )
  assert result.access_token == "access"


@pytest.mark.asyncio
async def test_register_endpoint_rejects_duplicate_email() -> None:
  """Retorna 409 quando o email já existe."""
  body = RegisterRequest(email="dup@x.com", name="Dup", password="pass")
  session = AsyncMock()
  response = MagicMock()

  existing_user = type("User", (), {"id": "existing"})()

  with patch(
    "app.entities.identity.router.get_user_by_email",
    new=AsyncMock(return_value=existing_user),
  ):
    with pytest.raises(HTTPException) as exc:
      await register_local(body=body, response=response, session=session)

  assert exc.value.status_code == 409
