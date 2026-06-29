from __future__ import annotations

import logging

from fastapi import HTTPException, status

from shared.events.redis_client import get_redis

logger = logging.getLogger(__name__)


async def enforce_rate_limit(*, key: str, max_attempts: int, window_seconds: int) -> None:
  """Limita tentativas por janela com contador no Redis (compartilhado entre instâncias).

  Lança HTTP 429 quando `max_attempts` é excedido dentro de `window_seconds`.
  """
  redis = get_redis()
  redis_key = f"ratelimit:{key}"
  try:
    current = await redis.incr(redis_key)
    if current == 1:
      await redis.expire(redis_key, window_seconds)
  except Exception:
    # Fail-open: indisponibilidade do Redis não pode derrubar a autenticação;
    # o evento fica registrado para investigação.
    logger.warning("rate limit indisponível (erro no Redis); liberando requisição", exc_info=True)
    return

  if current > max_attempts:
    raise HTTPException(
      status_code=status.HTTP_429_TOO_MANY_REQUESTS,
      detail="too many attempts, try again later",
      headers={"Retry-After": str(window_seconds)},
    )
