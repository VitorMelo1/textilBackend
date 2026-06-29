from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from shared.security.rate_limit import enforce_rate_limit


class FakeRedis:
  def __init__(self) -> None:
    self.counts: dict[str, int] = {}
    self.ttls: dict[str, int] = {}

  async def incr(self, key: str) -> int:
    self.counts[key] = self.counts.get(key, 0) + 1
    return self.counts[key]

  async def expire(self, key: str, ttl: int) -> None:
    self.ttls[key] = ttl


class BrokenRedis:
  async def incr(self, key: str) -> int:
    raise ConnectionError("redis down")


@pytest.mark.asyncio
async def test_enforce_rate_limit_allows_under_limit() -> None:
  fake = FakeRedis()
  with patch("shared.security.rate_limit.get_redis", return_value=fake):
    for _ in range(3):
      await enforce_rate_limit(key="t:allow", max_attempts=3, window_seconds=60)
  assert fake.counts["ratelimit:t:allow"] == 3
  assert fake.ttls["ratelimit:t:allow"] == 60


@pytest.mark.asyncio
async def test_enforce_rate_limit_blocks_over_limit_with_429() -> None:
  fake = FakeRedis()
  with patch("shared.security.rate_limit.get_redis", return_value=fake):
    for _ in range(3):
      await enforce_rate_limit(key="t:block", max_attempts=3, window_seconds=60)
    with pytest.raises(HTTPException) as exc:
      await enforce_rate_limit(key="t:block", max_attempts=3, window_seconds=60)
  assert exc.value.status_code == 429
  assert exc.value.headers is not None
  assert exc.value.headers["Retry-After"] == "60"


@pytest.mark.asyncio
async def test_enforce_rate_limit_fails_open_when_redis_unavailable() -> None:
  with patch("shared.security.rate_limit.get_redis", return_value=BrokenRedis()):
    await enforce_rate_limit(key="t:open", max_attempts=1, window_seconds=60)
