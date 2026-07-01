from __future__ import annotations

import os
import sys
from urllib.parse import urlparse


REQUIRED_ENV = [
  "ENV",
  "DATABASE_URL",
  "REDIS_URL",
  "JWT_SECRET",
  "SESSION_SECRET",
  "CORE_API_BASE_URL",
  "CHAT_SERVICE_BASE_URL",
  "CORS_ORIGINS",
  "STRIPE_SECRET_KEY",
  "STRIPE_WEBHOOK_SECRET",
  "STRIPE_PRICE_BASIC",
  "STRIPE_PRICE_PROFESSIONAL",
  "STRIPE_PRICE_ENTERPRISE",
  "STRIPE_CONNECT_RETURN_URL",
  "STRIPE_CONNECT_REFRESH_URL",
]

PLACEHOLDER_VALUES = {"change-me-in-dev", "change-me", "changeme", "secret", "dev-secret"}


def _is_https_url(value: str) -> bool:
  parsed = urlparse(value)
  return parsed.scheme == "https" and bool(parsed.netloc)


def main() -> int:
  problems: list[str] = []
  for key in REQUIRED_ENV:
    if not os.getenv(key):
      problems.append(f"{key} nao configurado")

  env = os.getenv("ENV", "").strip().lower()
  if env in {"", "dev", "development", "local", "test", "testing"}:
    problems.append("ENV precisa indicar producao/staging para este check")

  for key in ("JWT_SECRET", "SESSION_SECRET"):
    value = os.getenv(key, "").strip()
    if value.lower() in PLACEHOLDER_VALUES or len(value) < 32:
      problems.append(f"{key} precisa ter ao menos 32 caracteres e nao pode ser placeholder")

  if os.getenv("AUTH_COOKIE_SECURE", "").strip().lower() not in {"true", "1", "yes"}:
    problems.append("AUTH_COOKIE_SECURE precisa ser true em producao")

  for key in ("CORE_API_BASE_URL", "CHAT_SERVICE_BASE_URL", "STRIPE_CONNECT_RETURN_URL", "STRIPE_CONNECT_REFRESH_URL"):
    value = os.getenv(key, "")
    if value and not _is_https_url(value):
      problems.append(f"{key} precisa usar HTTPS publico")

  stripe_key = os.getenv("STRIPE_SECRET_KEY", "")
  if stripe_key and not stripe_key.startswith("sk_live_"):
    problems.append("STRIPE_SECRET_KEY precisa ser chave live em producao")

  cors_origins = [item.strip() for item in os.getenv("CORS_ORIGINS", "").split(",") if item.strip()]
  if any(origin.startswith("http://") for origin in cors_origins):
    problems.append("CORS_ORIGINS nao deve conter origem http:// em producao")

  if problems:
    print("Production readiness check failed:")
    for problem in problems:
      print(f"- {problem}")
    return 1

  print("Production readiness check passed.")
  return 0


if __name__ == "__main__":
  sys.exit(main())
