from __future__ import annotations

import logging

from shared.config import get_settings

logger = logging.getLogger(__name__)

try:
  import sentry_sdk
except Exception:  # pragma: no cover
  sentry_sdk = None  # type: ignore[assignment]


def init_sentry(*, service_name: str) -> None:
  """Inicializa o Sentry quando SENTRY_DSN está definido; caso contrário é no-op."""
  settings = get_settings()
  if not settings.SENTRY_DSN:
    return
  if sentry_sdk is None:
    logger.warning("SENTRY_DSN definido mas sentry-sdk não está instalado; monitoramento desativado")
    return
  sentry_sdk.init(
    dsn=settings.SENTRY_DSN,
    environment=settings.ENV,
    traces_sample_rate=0.1,
  )
  sentry_sdk.set_tag("service", service_name)
