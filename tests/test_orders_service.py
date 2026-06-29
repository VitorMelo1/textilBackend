from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.entities.orders import service
from app.entities.orders.schemas import OrderCreate


def test_compute_days_until_deadline() -> None:
  assert service.compute_days_until_deadline(date.today() + timedelta(days=3)) == 3


@pytest.mark.asyncio
async def test_create_order_rejects_duplicate_code() -> None:
  session = AsyncMock()
  body = OrderCreate(
    order_code="PED-001",
    client_name="Cliente",
    product_name="Produto",
    quantity=10,
    deadline=date.today(),
  )
  with patch("app.entities.orders.service.repo.get_order_by_code", new=AsyncMock(return_value=object())):
    with pytest.raises(HTTPException) as exc:
      await service.create(session, organization_id="org-1", body=body)
  assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_get_order_cross_org_returns_404() -> None:
  session = AsyncMock()
  row = type("Order", (), {"organization_id": "org-2"})()
  with patch("app.entities.orders.service.repo.get_order_by_id", new=AsyncMock(return_value=row)):
    with pytest.raises(HTTPException) as exc:
      await service.get_by_id(session, organization_id="org-1", order_id="o1")
  assert exc.value.status_code == 404
