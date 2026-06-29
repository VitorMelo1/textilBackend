from __future__ import annotations

from redis.asyncio import Redis

from ..config import get_settings


_redis: Redis | None = None


def get_redis() -> Redis:
  global _redis
  if _redis is None:
    settings = get_settings()
    _redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
  return _redis
