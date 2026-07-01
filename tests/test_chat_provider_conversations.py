from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.entities.chat import service


@pytest.mark.asyncio
async def test_provider_conversation_requires_real_provider_owner() -> None:
  session = AsyncMock()
  provider = SimpleNamespace(id="prov-1", organization_id=None, name="Prestador sem conta")

  with patch("app.entities.chat.service.repo.get_provider", new=AsyncMock(return_value=provider)):
    with pytest.raises(HTTPException) as exc:
      await service.get_or_create_provider_conversation(
        session,
        requester_organization_id="org-a",
        requester_user_id="user-a",
        provider_id="prov-1",
      )

  assert exc.value.status_code == 409
  assert exc.value.detail == "provider is not linked to an active organization"


@pytest.mark.asyncio
async def test_provider_conversation_adds_members_from_both_organizations() -> None:
  session = AsyncMock()
  provider = SimpleNamespace(id="prov-1", organization_id="org-b", name="Facção Real")
  created = SimpleNamespace(
    id="conv-1",
    organization_id="org-a",
    title="Facção Real",
    provider_id="prov-1",
    interest_request_id=None,
  )

  with (
    patch("app.entities.chat.service.repo.get_provider", new=AsyncMock(return_value=provider)),
    patch("app.entities.chat.service.repo.get_provider_conversation", new=AsyncMock(return_value=None)),
    patch("app.entities.chat.service.repo.list_active_chat_member_user_ids", new=AsyncMock(return_value=["user-b"])),
    patch("app.entities.chat.service.repo.create_provider_conversation", new=AsyncMock(return_value=created)) as create_mock,
  ):
    result = await service.get_or_create_provider_conversation(
      session,
      requester_organization_id="org-a",
      requester_user_id="user-a",
      provider_id="prov-1",
    )

  assert result.id == "conv-1"
  create_mock.assert_awaited_once()
  assert create_mock.await_args.kwargs["members"] == [
    ("org-a", "user-a"),
    ("org-b", "user-b"),
  ]


@pytest.mark.asyncio
async def test_provider_conversation_reuses_existing_conversation() -> None:
  session = AsyncMock()
  provider = SimpleNamespace(id="prov-1", organization_id="org-b", name="Facção Real")
  existing = SimpleNamespace(
    id="conv-1",
    organization_id="org-a",
    title="Facção Real",
    provider_id="prov-1",
    interest_request_id=None,
  )

  with (
    patch("app.entities.chat.service.repo.get_provider", new=AsyncMock(return_value=provider)),
    patch("app.entities.chat.service.repo.get_provider_conversation", new=AsyncMock(return_value=existing)),
    patch("app.entities.chat.service.repo.create_provider_conversation", new=AsyncMock()) as create_mock,
  ):
    result = await service.get_or_create_provider_conversation(
      session,
      requester_organization_id="org-a",
      requester_user_id="user-a",
      provider_id="prov-1",
    )

  assert result.id == "conv-1"
  create_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_interest_conversation_uses_interest_context() -> None:
  session = AsyncMock()
  interest = SimpleNamespace(
    id="interest-1",
    organization_id="org-a",
    requester_user_id="user-a",
    provider_id="prov-1",
  )
  provider = SimpleNamespace(id="prov-1", organization_id="org-b", name="Facção Real")
  created = SimpleNamespace(
    id="conv-1",
    organization_id="org-a",
    title="Facção Real",
    provider_id="prov-1",
    interest_request_id="interest-1",
    order_id=None,
  )

  with (
    patch("app.entities.chat.service.repo.get_interest_request", new=AsyncMock(return_value=interest)),
    patch("app.entities.chat.service.repo.get_provider", new=AsyncMock(return_value=provider)),
    patch("app.entities.chat.service.repo.get_interest_conversation", new=AsyncMock(return_value=None)),
    patch("app.entities.chat.service.repo.list_active_chat_member_user_ids", new=AsyncMock(return_value=["user-b"])),
    patch("app.entities.chat.service.repo.create_provider_conversation", new=AsyncMock(return_value=created)) as create_mock,
  ):
    result = await service.get_or_create_interest_conversation(
      session,
      requester_organization_id="org-a",
      requester_user_id="user-a",
      interest_request_id="interest-1",
    )

  assert result.interest_request_id == "interest-1"
  create_mock.assert_awaited_once()
  assert create_mock.await_args.kwargs["interest_request_id"] == "interest-1"


@pytest.mark.asyncio
async def test_order_conversation_is_limited_to_own_order() -> None:
  session = AsyncMock()
  order = SimpleNamespace(id="order-1", organization_id="org-b", order_code="PED-1")

  with patch("app.entities.chat.service.repo.get_order", new=AsyncMock(return_value=order)):
    with pytest.raises(HTTPException) as exc:
      await service.get_or_create_order_conversation(
        session,
        organization_id="org-a",
        requester_user_id="user-a",
        order_id="order-1",
      )

  assert exc.value.status_code == 404
  assert exc.value.detail == "order not found"
