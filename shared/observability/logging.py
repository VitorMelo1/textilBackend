from __future__ import annotations

import json
import logging
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_access_logger = logging.getLogger("textil.access")


class JsonLogFormatter(logging.Formatter):
  """Logs em JSON (uma linha por evento) com request-id quando disponível."""

  def format(self, record: logging.LogRecord) -> str:
    payload: dict[str, object] = {
      "ts": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S%z"),
      "level": record.levelname,
      "logger": record.name,
      "message": record.getMessage(),
    }
    request_id = request_id_var.get()
    if request_id:
      payload["request_id"] = request_id
    extra_fields = getattr(record, "extra_fields", None)
    if isinstance(extra_fields, dict):
      payload.update(extra_fields)
    if record.exc_info:
      payload["exc_info"] = self.formatException(record.exc_info)
    return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> None:
  handler = logging.StreamHandler()
  handler.setFormatter(JsonLogFormatter())
  root = logging.getLogger()
  root.handlers = [handler]
  root.setLevel(level)


class RequestContextMiddleware(BaseHTTPMiddleware):
  """Atribui um request-id por requisição e emite log de acesso estruturado."""

  async def dispatch(self, request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    token = request_id_var.set(request_id)
    started = time.perf_counter()
    try:
      response = await call_next(request)
      duration_ms = round((time.perf_counter() - started) * 1000, 1)
      response.headers["X-Request-ID"] = request_id
      _access_logger.info(
        "request",
        extra={
          "extra_fields": {
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
          }
        },
      )
      return response
    except Exception:
      duration_ms = round((time.perf_counter() - started) * 1000, 1)
      _access_logger.exception(
        "request failed",
        extra={
          "extra_fields": {
            "method": request.method,
            "path": request.url.path,
            "duration_ms": duration_ms,
          }
        },
      )
      raise
    finally:
      request_id_var.reset(token)
