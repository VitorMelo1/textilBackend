from __future__ import annotations

import pytest

from shared.config import Settings


def make_settings(**overrides: object) -> Settings:
  base: dict[str, object] = {
    "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/db",
    "REDIS_URL": "redis://localhost:6379/0",
    "JWT_SECRET": "x" * 48,
  }
  base.update(overrides)
  return Settings(_env_file=None, **base)  # type: ignore[arg-type]


def test_dev_accepts_placeholder_secret() -> None:
  s = make_settings(ENV="dev", JWT_SECRET="change-me-in-dev")
  assert s.JWT_SECRET == "change-me-in-dev"


def test_production_rejects_placeholder_jwt_secret() -> None:
  with pytest.raises(ValueError, match="JWT_SECRET"):
    make_settings(ENV="prod", JWT_SECRET="change-me-in-dev")


def test_production_rejects_short_jwt_secret() -> None:
  with pytest.raises(ValueError, match="JWT_SECRET"):
    make_settings(ENV="prod", JWT_SECRET="curta")


def test_production_rejects_placeholder_session_secret() -> None:
  with pytest.raises(ValueError, match="SESSION_SECRET"):
    make_settings(ENV="prod", SESSION_SECRET="change-me-in-dev")


def test_production_forces_secure_cookie() -> None:
  s = make_settings(ENV="prod", AUTH_COOKIE_SECURE=False)
  assert s.AUTH_COOKIE_SECURE is True


def test_production_accepts_strong_config() -> None:
  s = make_settings(ENV="production", SESSION_SECRET="y" * 40)
  assert s.AUTH_COOKIE_SECURE is True
