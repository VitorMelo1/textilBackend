from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.entities.costs import service
from app.entities.costs.schemas import CostCalculationCreate


def test_calc_suggested_price() -> None:
  assert round(service.calc_suggested_price(10, 40), 2) == 14.0


@pytest.mark.asyncio
async def test_get_cost_cross_org_returns_404() -> None:
  session = AsyncMock()
  row = type("Calc", (), {"organization_id": "org-2"})()
  with patch("app.entities.costs.service.repo.get_calculation", new=AsyncMock(return_value=row)):
    with pytest.raises(HTTPException) as exc:
      await service.get_by_id(session, organization_id="org-1", calculation_id="c1")
  assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_create_cost_recalculates_defaults() -> None:
  session = AsyncMock()
  calc = type(
    "Calc",
    (),
    {
      "id": "c1",
      "organization_id": "org-1",
      "product_name": "Produto",
      "quantity": 10,
      "total_material_cost": 0,
      "total_labor_cost": 0,
      "total_cost": 0,
      "cost_per_unit": 0,
      "profit_margin": 20,
      "suggested_price": 0,
      "created_at": datetime.now(timezone.utc),
      "updated_at": datetime.now(timezone.utc),
    },
  )()
  with (
    patch("app.entities.costs.service.repo.create_calculation", new=AsyncMock(return_value=calc)),
    patch("app.entities.costs.service.repo.list_materials", new=AsyncMock(return_value=[])),
    patch("app.entities.costs.service.repo.list_labor", new=AsyncMock(return_value=[])),
  ):
    out = await service.create(
      session,
      organization_id="org-1",
      body=CostCalculationCreate(product_name="Produto", quantity=10, profit_margin=20),
    )
  assert out.suggested_price == 0.0
