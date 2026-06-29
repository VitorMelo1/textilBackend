from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.events.redis_client import get_redis

logger = logging.getLogger(__name__)


async def readiness_checks(session: AsyncSession) -> dict[str, str]:
  """Valida dependências reais (Postgres e Redis) para o endpoint /ready."""
  checks: dict[str, str] = {}
  try:
    await session.execute(text("SELECT 1"))
    checks["database"] = "ok"
  except Exception:
    logger.warning("readiness: banco de dados indisponível", exc_info=True)
    checks["database"] = "unavailable"
  try:
    await get_redis().ping()
    checks["redis"] = "ok"
  except Exception:
    logger.warning("readiness: redis indisponível", exc_info=True)
    checks["redis"] = "unavailable"
  return checks
