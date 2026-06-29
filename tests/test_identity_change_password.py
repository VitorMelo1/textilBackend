"""
Testes para POST /auth/change-password:
- hash_password / verify_password round-trip
- ChangePasswordRequest schema
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.entities.identity.schemas import ChangePasswordRequest
from shared.security.passwords import hash_password, verify_password


# ---------------------------------------------------------------------------
# Utilitários de senha
# ---------------------------------------------------------------------------


def test_hash_and_verify_password_round_trip() -> None:
  """hash_password gera um hash e verify_password confirma a senha correta."""
  hashed = hash_password("secret")
  assert hashed != "secret"
  assert verify_password("secret", hashed) is True


def test_verify_password_rejects_wrong_password() -> None:
  """verify_password retorna False para senha incorreta."""
  hashed = hash_password("secret")
  assert verify_password("wrong", hashed) is False


# ---------------------------------------------------------------------------
# Schema: ChangePasswordRequest
# ---------------------------------------------------------------------------


def test_change_password_request_validates_required_fields() -> None:
  """ChangePasswordRequest aceita current_password e new_password."""
  req = ChangePasswordRequest(current_password="old", new_password="newpass123")
  assert req.current_password == "old"
  assert req.new_password == "newpass123"


def test_change_password_request_requires_current_password() -> None:
  """ChangePasswordRequest sem current_password deve lançar ValidationError."""
  with pytest.raises(ValidationError):
    ChangePasswordRequest(new_password="new")  # type: ignore[call-arg]


def test_change_password_request_requires_new_password() -> None:
  """ChangePasswordRequest sem new_password deve lançar ValidationError."""
  with pytest.raises(ValidationError):
    ChangePasswordRequest(current_password="old")  # type: ignore[call-arg]
