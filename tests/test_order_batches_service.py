from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.entities.orders import service
from app.entities.orders.schemas import OrderBatchCreate, OrderBatchUpdate


@pytest.mark.asyncio
async def test_create_batch_requires_existing_order() -> None:
  session = AsyncMock()
  body = OrderBatchCreate(lot_number="L1", quantity_sent=10)
  with patch("app.entities.orders.service.repo.get_order_by_id", new=AsyncMock(return_value=None)):
    with pytest.raises(HTTPException) as exc:
      await service.create_batch(
        session,
        organization_id="org-1",
        order_id="o1",
        body=body,
      )
  assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_update_batch_cross_org_returns_404() -> None:
  session = AsyncMock()
  row = type("Batch", (), {"organization_id": "org-2"})()
  with patch("app.entities.orders.service.repo.get_batch_by_id", new=AsyncMock(return_value=row)):
    with pytest.raises(HTTPException) as exc:
      await service.update_batch(
        session,
        organization_id="org-1",
        batch_id="b1",
        body=OrderBatchUpdate(status="pending"),
      )
  assert exc.value.status_code == 404
