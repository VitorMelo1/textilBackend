from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.entities.favorites import service


@pytest.mark.asyncio
async def test_create_favorite_requires_existing_provider() -> None:
  session = AsyncMock()
  with patch("app.entities.favorites.service.repo.get_provider", new=AsyncMock(return_value=None)):
    with pytest.raises(HTTPException) as exc:
      await service.create(
        session,
        organization_id="org-1",
        user_id="user-1",
        provider_id="prov-1",
      )
  assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_create_favorite_rejects_duplicate() -> None:
  session = AsyncMock()
  provider = type(
    "Provider",
    (),
    {
      "id": "prov-1",
      "name": "P",
      "provider_type": "B",
      "location": None,
      "rating": 5,
      "review_count": 10,
      "verified": True,
    },
  )()
  existing = type("Favorite", (), {})()
  with (
    patch("app.entities.favorites.service.repo.get_provider", new=AsyncMock(return_value=provider)),
    patch("app.entities.favorites.service.repo.get_favorite", new=AsyncMock(return_value=existing)),
  ):
    with pytest.raises(HTTPException) as exc:
      await service.create(
        session,
        organization_id="org-1",
        user_id="user-1",
        provider_id="prov-1",
      )
  assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_delete_favorite_not_found() -> None:
  session = AsyncMock()
  with patch("app.entities.favorites.service.repo.delete_favorite", new=AsyncMock(return_value=False)):
    with pytest.raises(HTTPException) as exc:
      await service.delete(
        session,
        organization_id="org-1",
        user_id="user-1",
        provider_id="prov-1",
      )
  assert exc.value.status_code == 404
