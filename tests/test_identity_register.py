"""
Testes para a lógica de registro: repo + schemas.
Não importa o router (que requer asyncpg via shared.db.session).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.entities.identity.repo import create_local_user_with_org
from app.entities.identity.schemas import RegisterRequest
from shared.db.models import Organization


# ---------------------------------------------------------------------------
# Repo: create_local_user_with_org
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_local_user_defaults_user_type_when_omitted() -> None:
  """Sem user_type explícito, User recebe 'confeccao' como padrão."""
  session = AsyncMock()
  session.add = MagicMock()

  with patch("app.entities.identity.repo.hash_password", return_value="hashed"):
    user, member = await create_local_user_with_org(
      session,
      email="owner@x.com",
      name="Owner",
      password="pass",
      organization_name=None,
    )

  assert user.user_type == "confeccao"
  assert user.business_profile is None
  assert member.role == "owner"
  assert member.member_status == "active"


@pytest.mark.asyncio
async def test_create_local_user_persists_business_profile_and_user_type() -> None:
  """business_profile e user_type passados são gravados no objeto User."""
  session = AsyncMock()
  session.add = MagicMock()

  with patch("app.entities.identity.repo.hash_password", return_value="hashed"):
    user, member = await create_local_user_with_org(
      session,
      email="atelier@x.com",
      name="Atelier Owner",
      password="pass",
      organization_name="Atelier SA",
      business_profile="atelier",
      user_type="faccao",
    )

  assert user.business_profile == "atelier"
  assert user.user_type == "faccao"
  assert member.role == "owner"


@pytest.mark.asyncio
async def test_create_local_user_org_name_fallback() -> None:
  """Sem organization_name, org recebe '<name> - Org'."""
  session = AsyncMock()
  session.add = MagicMock()

  with patch("app.entities.identity.repo.hash_password", return_value="hashed"):
    await create_local_user_with_org(
      session,
      email="solo@x.com",
      name="Solo User",
      password="pass",
      organization_name=None,
    )

  added = [call.args[0] for call in session.add.call_args_list]
  orgs = [o for o in added if isinstance(o, Organization)]
  assert len(orgs) == 1
  assert orgs[0].name == "Solo User - Org"


@pytest.mark.asyncio
async def test_create_local_user_member_is_active_owner() -> None:
  """Todo usuário registrado vira 'owner' + 'active' na organização."""
  session = AsyncMock()
  session.add = MagicMock()

  with patch("app.entities.identity.repo.hash_password", return_value="hashed"):
    _, member = await create_local_user_with_org(
      session,
      email="new@x.com",
      name="New",
      password="pass",
      organization_name=None,
    )

  assert member.role == "owner"
  assert member.member_status == "active"


# ---------------------------------------------------------------------------
# Schemas: RegisterRequest
# ---------------------------------------------------------------------------


def test_register_request_accepts_optional_profile_fields() -> None:
  """RegisterRequest valida sem erros com os novos campos opcionais."""
  req = RegisterRequest(
    email="test@x.com",
    name="Test",
    password="secret",
    business_profile="industry",
    user_type="confeccao",
  )
  assert req.business_profile == "industry"
  assert req.user_type == "confeccao"


def test_register_request_profile_fields_default_to_none() -> None:
  """Sem os campos, ficam None."""
  req = RegisterRequest(email="test@x.com", name="Test", password="secret")
  assert req.business_profile is None
  assert req.user_type is None
