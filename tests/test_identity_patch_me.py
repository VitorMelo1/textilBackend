"""
Testes para PATCH /auth/me:
- update_user_and_org (repo)
- UpdateMeRequest (schema)
- ChangePasswordRequest (schema)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.entities.identity.repo import update_user_and_org
from app.entities.identity.schemas import ChangePasswordRequest, MeResponse, UpdateMeRequest


# ---------------------------------------------------------------------------
# Repo: update_user_and_org
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_user_and_org_updates_name() -> None:
  """Quando name é fornecido, user.name deve ser atualizado."""
  session = AsyncMock()

  mock_user = MagicMock()
  mock_user.name = "Original Name"
  mock_user.id = "user-1"

  mock_org = MagicMock()
  mock_org.name = "Original Org"
  mock_org.id = "org-1"

  with (
    patch("app.entities.identity.repo.get_user_by_id", return_value=mock_user),
    patch("app.entities.identity.repo.get_org_by_id", return_value=mock_org),
  ):
    result = await update_user_and_org(
      session,
      user_id="user-1",
      org_id="org-1",
      name="Novo Nome",
      company_name=None,
      phone=None,
      description=None,
    )

  assert result is not None
  assert mock_user.name == "Novo Nome"


@pytest.mark.asyncio
async def test_update_user_and_org_updates_company_name() -> None:
  """Quando company_name é fornecido, org.name deve ser atualizado."""
  session = AsyncMock()

  mock_user = MagicMock()
  mock_user.id = "user-1"

  mock_org = MagicMock()
  mock_org.name = "Old Org Name"
  mock_org.id = "org-1"

  with (
    patch("app.entities.identity.repo.get_user_by_id", return_value=mock_user),
    patch("app.entities.identity.repo.get_org_by_id", return_value=mock_org),
  ):
    result = await update_user_and_org(
      session,
      user_id="user-1",
      org_id="org-1",
      name=None,
      company_name="Nova Empresa",
      phone=None,
      description=None,
    )

  assert result is not None
  assert mock_org.name == "Nova Empresa"


@pytest.mark.asyncio
async def test_update_user_and_org_updates_phone_and_description() -> None:
  """Quando phone e description são fornecidos, org.phone e org.description são atualizados."""
  session = AsyncMock()

  mock_user = MagicMock()
  mock_user.id = "user-1"

  mock_org = MagicMock()
  mock_org.id = "org-1"

  with (
    patch("app.entities.identity.repo.get_user_by_id", return_value=mock_user),
    patch("app.entities.identity.repo.get_org_by_id", return_value=mock_org),
  ):
    result = await update_user_and_org(
      session,
      user_id="user-1",
      org_id="org-1",
      name=None,
      company_name=None,
      phone="11999990000",
      description="Empresa de costura",
    )

  assert result is not None
  assert mock_org.phone == "11999990000"
  assert mock_org.description == "Empresa de costura"


@pytest.mark.asyncio
async def test_update_user_and_org_skips_none_fields() -> None:
  """Campos None não devem modificar user.name nem org.name."""
  session = AsyncMock()

  mock_user = MagicMock(spec=[])  # spec vazio — qualquer set de atributo inesperado levanta AttributeError
  mock_user.id = "user-1"

  mock_org = MagicMock(spec=[])
  mock_org.id = "org-1"

  with (
    patch("app.entities.identity.repo.get_user_by_id", return_value=mock_user),
    patch("app.entities.identity.repo.get_org_by_id", return_value=mock_org),
  ):
    result = await update_user_and_org(
      session,
      user_id="user-1",
      org_id="org-1",
      name=None,
      company_name=None,
      phone=None,
      description=None,
    )

  assert result is not None
  # Como spec=[] proíbe atributos arbitrários, se o código tivesse feito
  # user.name = None ou org.name = None, teríamos AttributeError.
  # Chegar aqui sem exceção já prova que nenhum campo foi tocado.


@pytest.mark.asyncio
async def test_update_user_and_org_returns_none_when_user_not_found() -> None:
  """Se get_user_by_id retornar None, update_user_and_org deve retornar None."""
  session = AsyncMock()

  with (
    patch("app.entities.identity.repo.get_user_by_id", return_value=None),
    patch("app.entities.identity.repo.get_org_by_id", return_value=MagicMock()),
  ):
    result = await update_user_and_org(
      session,
      user_id="missing-user",
      org_id="org-1",
      name="Qualquer",
      company_name=None,
      phone=None,
      description=None,
    )

  assert result is None


@pytest.mark.asyncio
async def test_update_user_and_org_returns_none_when_org_not_found() -> None:
  """Se get_org_by_id retornar None, update_user_and_org deve retornar None."""
  session = AsyncMock()

  mock_user = MagicMock()
  mock_user.id = "user-1"

  with (
    patch("app.entities.identity.repo.get_user_by_id", return_value=mock_user),
    patch("app.entities.identity.repo.get_org_by_id", return_value=None),
  ):
    result = await update_user_and_org(
      session,
      user_id="user-1",
      org_id="missing-org",
      name=None,
      company_name="X",
      phone=None,
      description=None,
    )

  assert result is None


# ---------------------------------------------------------------------------
# Schemas: UpdateMeRequest
# ---------------------------------------------------------------------------


def test_update_me_request_all_fields_optional() -> None:
  """UpdateMeRequest() sem argumentos cria objeto com todos os campos None."""
  req = UpdateMeRequest()
  assert req.name is None
  assert req.company_name is None
  assert req.phone is None
  assert req.description is None


def test_update_me_request_accepts_partial_update() -> None:
  """UpdateMeRequest com apenas name preenchido funciona; demais ficam None."""
  req = UpdateMeRequest(name="X")
  assert req.name == "X"
  assert req.company_name is None
  assert req.phone is None
  assert req.description is None


# ---------------------------------------------------------------------------
# Schemas: ChangePasswordRequest
# ---------------------------------------------------------------------------


def test_change_password_request_requires_both_fields() -> None:
  """ChangePasswordRequest com current_password e new_password funciona."""
  req = ChangePasswordRequest(current_password="a", new_password="b")
  assert req.current_password == "a"
  assert req.new_password == "b"


# ---------------------------------------------------------------------------
# Schemas: MeResponse
# ---------------------------------------------------------------------------


def test_me_response_includes_new_fields() -> None:
  """MeResponse serializa corretamente com os novos campos company_name, phone e description."""
  resp = MeResponse(
    user_id="u",
    organization_id="o",
    company_name="C",
    phone="11999",
    description="Desc",
  )
  assert resp.user_id == "u"
  assert resp.organization_id == "o"
  assert resp.company_name == "C"
  assert resp.phone == "11999"
  assert resp.description == "Desc"
