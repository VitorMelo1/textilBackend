from __future__ import annotations

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_DEV_ENVS = {"dev", "development", "local", "test", "testing"}
_PLACEHOLDER_SECRETS = {"change-me-in-dev", "change-me", "changeme", "secret", "dev-secret"}
_MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
  model_config = SettingsConfigDict(env_file=".env", extra="ignore")

  ENV: str = "dev"

  DATABASE_URL: str
  REDIS_URL: str

  JWT_SECRET: str
  JWT_ISSUER: str = "textilmarket"
  JWT_AUDIENCE: str = "textilmarket-web"
  SESSION_SECRET: str | None = None

  ACCESS_TOKEN_TTL_SECONDS: int = 900
  REFRESH_TOKEN_TTL_DAYS: int = 30
  AUTH_COOKIE_SECURE: bool = False
  AUTH_COOKIE_DOMAIN: str | None = None
  AUTH_COOKIE_SAMESITE: str = "lax"
  ACCESS_COOKIE_NAME: str = "textil_access_token"
  REFRESH_COOKIE_NAME: str = "textil_refresh_token"

  CORE_API_BASE_URL: str = "http://localhost:8000"
  CHAT_SERVICE_BASE_URL: str = "http://localhost:8001"

  # OAuth (Google)
  OAUTH_GOOGLE_CLIENT_ID: str | None = None
  OAUTH_GOOGLE_CLIENT_SECRET: str | None = None
  OAUTH_GOOGLE_REDIRECT_URI: str | None = None
  FRONTEND_OAUTH_REDIRECT: str | None = None

  # Stripe billing
  STRIPE_SECRET_KEY: str | None = None
  STRIPE_WEBHOOK_SECRET: str | None = None
  STRIPE_PRICE_BASIC: str | None = None
  STRIPE_PRICE_PROFESSIONAL: str | None = None
  STRIPE_PRICE_ENTERPRISE: str | None = None

  # Observabilidade (opcional): DSN do Sentry para monitoramento de erros.
  SENTRY_DSN: str | None = None
  INVITE_EMAIL_DELIVERY_ENABLED: bool = False

  # Origens permitidas para CORS (separadas por vírgula). Dev: Vite em :5173.
  CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

  @model_validator(mode="after")
  def _enforce_production_safety(self) -> Settings:
    # Guarda fail-safe: fora de dev/test a aplicação não pode subir com segredos
    # de exemplo (permitiriam forjar JWTs HS256) nem cookies de auth sem Secure.
    if self.ENV.strip().lower() in _DEV_ENVS:
      return self

    problems: list[str] = []
    jwt_secret = self.JWT_SECRET.strip()
    if jwt_secret.lower() in _PLACEHOLDER_SECRETS or len(jwt_secret) < _MIN_SECRET_LENGTH:
      problems.append(f"JWT_SECRET deve ter ao menos {_MIN_SECRET_LENGTH} caracteres e não pode ser valor de exemplo")
    if self.SESSION_SECRET is not None:
      session_secret = self.SESSION_SECRET.strip()
      if session_secret.lower() in _PLACEHOLDER_SECRETS or len(session_secret) < _MIN_SECRET_LENGTH:
        problems.append(
          f"SESSION_SECRET deve ter ao menos {_MIN_SECRET_LENGTH} caracteres e não pode ser valor de exemplo"
        )
    if problems:
      raise ValueError(f"Configuração insegura para ENV={self.ENV!r}: " + "; ".join(problems))

    # Cookies de sessão só trafegam por HTTPS fora de dev.
    self.AUTH_COOKIE_SECURE = True
    return self


_settings: Settings | None = None


def get_settings() -> Settings:
  global _settings
  if _settings is None:
    _settings = Settings()
  return _settings
