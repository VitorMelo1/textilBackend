from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from shared.db.session import get_db_session
from shared.observability.readiness import readiness_checks

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
  return {"status": "ok", "service": "core-api"}


@router.get("/ready")
async def ready(session: AsyncSession = Depends(get_db_session)) -> JSONResponse:
  checks = await readiness_checks(session)
  healthy = all(value == "ok" for value in checks.values())
  return JSONResponse(
    status_code=200 if healthy else 503,
    content={
      "status": "ready" if healthy else "unavailable",
      "service": "core-api",
      "checks": checks,
    },
  )
