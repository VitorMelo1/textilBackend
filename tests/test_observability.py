from __future__ import annotations

import json
import logging
from unittest.mock import AsyncMock, patch

import pytest

from shared.observability.logging import JsonLogFormatter, request_id_var
from shared.observability.readiness import readiness_checks


def test_json_formatter_outputs_structured_record() -> None:
  formatter = JsonLogFormatter()
  record = logging.LogRecord("textil", logging.INFO, __file__, 1, "hello %s", ("world",), None)
  token = request_id_var.set("req-123")
  try:
    payload = json.loads(formatter.format(record))
  finally:
    request_id_var.reset(token)

  assert payload["level"] == "INFO"
  assert payload["logger"] == "textil"
  assert payload["message"] == "hello world"
  assert payload["request_id"] == "req-123"


class PingOkRedis:
  async def ping(self) -> bool:
    return True


class PingBrokenRedis:
  async def ping(self) -> bool:
    raise ConnectionError("redis down")


@pytest.mark.asyncio
async def test_readiness_all_ok() -> None:
  session = AsyncMock()
  with patch("shared.observability.readiness.get_redis", return_value=PingOkRedis()):
    checks = await readiness_checks(session)
  assert checks == {"database": "ok", "redis": "ok"}


@pytest.mark.asyncio
async def test_readiness_reports_failures() -> None:
  session = AsyncMock()
  session.execute.side_effect = ConnectionError("db down")
  with patch("shared.observability.readiness.get_redis", return_value=PingBrokenRedis()):
    checks = await readiness_checks(session)
  assert checks == {"database": "unavailable", "redis": "unavailable"}
