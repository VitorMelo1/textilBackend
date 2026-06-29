from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.entities.reviews.service import refresh_provider_reputation


@pytest.mark.asyncio
async def test_refresh_provider_reputation_updates_aggregates() -> None:
  provider = SimpleNamespace(id="p1", rating=0, review_count=0)
  session = AsyncMock()
  result = MagicMock()
  result.one.return_value = (3, Decimal("4.3333"))
  session.execute.return_value = result

  await refresh_provider_reputation(session, provider)  # type: ignore[arg-type]

  assert provider.review_count == 3
  assert provider.rating == pytest.approx(4.3333)


@pytest.mark.asyncio
async def test_refresh_provider_reputation_handles_no_reviews() -> None:
  provider = SimpleNamespace(id="p1", rating=4.5, review_count=9)
  session = AsyncMock()
  result = MagicMock()
  result.one.return_value = (0, None)
  session.execute.return_value = result

  await refresh_provider_reputation(session, provider)  # type: ignore[arg-type]

  assert provider.review_count == 0
  assert provider.rating == 0.0
