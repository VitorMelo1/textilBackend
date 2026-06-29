from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.entities.costs import service
from app.entities.costs.schemas import CostCalculationLaborCreate, CostCalculationMaterialCreate


@pytest.mark.asyncio
async def test_create_material_requires_calculation() -> None:
  session = AsyncMock()
  with patch(
    "app.entities.costs.service.ensure_calculation_for_org",
    new=AsyncMock(side_effect=HTTPException(status_code=404, detail="x")),
  ):
    with pytest.raises(HTTPException) as exc:
      await service.create_material(
        session,
        organization_id="org-1",
        calculation_id="c1",
        body=CostCalculationMaterialCreate(name="Mat", quantity=2, unit="m", unit_cost=3),
      )
  assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_create_labor_maps_total() -> None:
  session = AsyncMock()
  calc = type("Calc", (), {"id": "c1"})()
  labor = type(
    "Labor",
    (),
    {
      "id": "l1",
      "organization_id": "org-1",
      "calculation_id": "c1",
      "description": "Costura",
      "hours": 2,
      "hourly_rate": 15,
      "total_cost": 30,
      "sort_order": 0,
      "created_at": datetime.now(timezone.utc),
      "updated_at": datetime.now(timezone.utc),
    },
  )()
  with (
    patch("app.entities.costs.service.ensure_calculation_for_org", new=AsyncMock(return_value=calc)),
    patch("app.entities.costs.service.repo.create_labor", new=AsyncMock(return_value=labor)),
    patch("app.entities.costs.service.recalculate_totals", new=AsyncMock(return_value=None)),
  ):
    out = await service.create_labor(
      session,
      organization_id="org-1",
      calculation_id="c1",
      body=CostCalculationLaborCreate(description="Costura", hours=2, hourly_rate=15),
    )
  assert out.total_cost == 30
