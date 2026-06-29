"""
Testes de integração do endpoint PATCH /technical-sheets/{id}.
Requerem asyncpg — pulados se não estiver instalado.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("asyncpg")

from fastapi import HTTPException  # noqa: E402

from app.entities.technical_sheets.router import update_sheet  # noqa: E402
from app.entities.technical_sheets.schemas import TechnicalSheetOut, TechnicalSheetUpdate  # noqa: E402


def _fake_sheet(**kwargs):
  defaults = dict(
    id="sheet-1",
    organization_id="org-1",
    fabric="Malha",
    status="pending",
    observations=None,
    size_grade_type="letter",
    sizes_json='{"M": 10}',
    total_pieces=10,
    created_at=None,
  )
  defaults.update(kwargs)
  return type("Sheet", (), defaults)()


def _fake_claims(org: str = "org-1"):
  return type("Claims", (), {"org": org})()


@pytest.mark.asyncio
async def test_patch_sheet_returns_404_when_not_found() -> None:
  """PATCH retorna 404 se a ficha não pertence à organização."""
  session = AsyncMock()
  result_mock = MagicMock()
  result_mock.scalar_one_or_none.return_value = None
  session.execute = AsyncMock(return_value=result_mock)

  with pytest.raises(HTTPException) as exc:
    await update_sheet(
      sheet_id="missing",
      body=TechnicalSheetUpdate(fabric="Novo"),
      claims=_fake_claims(),
      session=session,
    )
  assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_patch_sheet_updates_fabric_and_status() -> None:
  """PATCH atualiza fabric e status no objeto da sessão e faz commit."""
  sheet = _fake_sheet()
  session = AsyncMock()

  call_count = 0

  async def fake_execute(_q):
    nonlocal call_count
    result = MagicMock()
    if call_count == 0:
      result.scalar_one_or_none.return_value = sheet
    else:
      result.scalars.return_value.all.return_value = []
    call_count += 1
    return result

  session.execute = fake_execute

  with patch(
    "app.entities.technical_sheets.router._sheet_out",
    new=AsyncMock(return_value=MagicMock(spec=TechnicalSheetOut)),
  ):
    await update_sheet(
      sheet_id="sheet-1",
      body=TechnicalSheetUpdate(fabric="Jeans Premium", status="in_production"),
      claims=_fake_claims(),
      session=session,
    )

  assert sheet.fabric == "Jeans Premium"
  assert sheet.status == "in_production"
  session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_patch_sheet_skips_none_fields() -> None:
  """Campos não enviados não sobrescrevem os dados existentes."""
  sheet = _fake_sheet(fabric="Original", status="pending")
  session = AsyncMock()

  call_count = 0

  async def fake_execute(_q):
    nonlocal call_count
    result = MagicMock()
    if call_count == 0:
      result.scalar_one_or_none.return_value = sheet
    else:
      result.scalars.return_value.all.return_value = []
    call_count += 1
    return result

  session.execute = fake_execute

  with patch(
    "app.entities.technical_sheets.router._sheet_out",
    new=AsyncMock(return_value=MagicMock(spec=TechnicalSheetOut)),
  ):
    await update_sheet(
      sheet_id="sheet-1",
      body=TechnicalSheetUpdate(observations="nova obs"),
      claims=_fake_claims(),
      session=session,
    )

  assert sheet.fabric == "Original"
  assert sheet.status == "pending"
  assert sheet.observations == "nova obs"
