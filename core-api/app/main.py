from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .api.health import router as health_router
from .entities.identity.router import router as auth_router
from .entities.organizations.router import router as organizations_router
from .entities.technical_sheets.router import router as technical_sheets_router
from .entities.network.router import router as network_router
from .entities.reviews.router import router as reviews_router
from .entities.chat.router import router as chat_router
from .entities.favorites.router import router as favorites_router
from .entities.interest_requests.router import router as interest_requests_router
from .entities.team.router import router as team_router
from .entities.orders.router import batch_router as order_batches_router
from .entities.orders.router import router as orders_router
from .entities.inventory.router import router as inventory_router
from .entities.costs.router import labor_router as cost_labor_router
from .entities.costs.router import material_router as cost_materials_router
from .entities.costs.router import router as costs_router
from .entities.marketplace_payments.router import router as marketplace_payments_router
from .entities.plans.router import router as plans_router
from shared.config import get_settings
from shared.observability.logging import RequestContextMiddleware, configure_logging
from shared.observability.sentry import init_sentry


def create_app() -> FastAPI:
  configure_logging()
  init_sentry(service_name="core-api")
  app = FastAPI(title="Duonekso Core API")
  settings = get_settings()
  cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
  app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
  )
  app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET or settings.JWT_SECRET)
  app.add_middleware(RequestContextMiddleware)
  app.include_router(health_router)
  app.include_router(auth_router)
  app.include_router(organizations_router)
  app.include_router(technical_sheets_router)
  app.include_router(network_router)
  app.include_router(reviews_router)
  app.include_router(chat_router)
  app.include_router(favorites_router)
  app.include_router(interest_requests_router)
  app.include_router(team_router)
  app.include_router(orders_router)
  app.include_router(order_batches_router)
  app.include_router(inventory_router)
  app.include_router(costs_router)
  app.include_router(cost_materials_router)
  app.include_router(cost_labor_router)
  app.include_router(marketplace_payments_router)
  app.include_router(plans_router)
  return app


app = create_app()
