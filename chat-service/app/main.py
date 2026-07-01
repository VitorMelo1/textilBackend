from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.config import get_settings
from shared.observability.logging import RequestContextMiddleware, configure_logging
from shared.observability.sentry import init_sentry

from .api.health import router as health_router
from .entities.chat.router import router as chat_router


def create_app() -> FastAPI:
  configure_logging()
  init_sentry(service_name="chat-service")
  app = FastAPI(title="Duonekso Chat Service")
  settings = get_settings()
  cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
  # O frontend consome o backfill REST deste serviço em outra origem (porta 8001).
  app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
  )
  app.add_middleware(RequestContextMiddleware)
  app.include_router(health_router)
  app.include_router(chat_router)
  return app


app = create_app()
