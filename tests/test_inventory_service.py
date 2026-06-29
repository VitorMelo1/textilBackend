from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.entities.inventory import service
from app.entities.inventory.schemas import InventoryItemCreate, InventoryMovementCreate


@pytest.mark.asyncio
async def test_get_item_cross_org_returns_404() -> None:
  session = AsyncMock()
  row = type("Item", (), {"organization_id": "org-2"})()
  with patch("app.entities.inventory.service.repo.get_item", new=AsyncMock(return_value=row)):
    with pytest.raises(HTTPException) as exc:
      await service.get_item(session, organization_id="org-1", item_id="i1")
  assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_create_item_maps_output() -> None:
  session = AsyncMock()
  body = InventoryItemCreate(
    name="Tecido",
    category="tecido",
    current_stock=10,
    min_stock=20,
    unit="metro",
    unit_cost=3.5,
  )
  row = type(
    "Item",
    (),
    {
      "id": "i1",
      "organization_id": "org-1",
      "name": "Tecido",
      "category": "tecido",
      "current_stock": 10,
      "min_stock": 20,
      "unit": "metro",
      "unit_cost": 3.5,
      "supplier": None,
      "created_at": datetime.now(timezone.utc),
      "updated_at": datetime.now(timezone.utc),
    },
  )()
  with patch("app.entities.inventory.service.repo.create_item", new=AsyncMock(return_value=row)):
    out = await service.create_item(session, organization_id="org-1", body=body)
  assert out.id == "i1"
  assert out.is_below_min is True


@pytest.mark.asyncio
async def test_create_saida_movement_with_insufficient_stock() -> None:
  session = AsyncMock()
  item = type("Item", (), {"organization_id": "org-1", "current_stock": 2.0})()
  body = InventoryMovementCreate(movement_type="saida", quantity=3, reason="teste")
  with patch("app.entities.inventory.service.repo.get_item", new=AsyncMock(return_value=item)):
    with pytest.raises(HTTPException) as exc:
      await service.create_movement(
        session,
        organization_id="org-1",
        item_id="i1",
        user_id="u1",
        body=body,
      )
  assert exc.value.status_code == 400
