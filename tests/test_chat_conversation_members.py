from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.entities.chat.service import find_missing_org_members


def _result_with_rows(rows: list[tuple[str]]) -> MagicMock:
  result = MagicMock()
  result.__iter__ = MagicMock(return_value=iter(rows))
  return result


@pytest.mark.asyncio
async def test_all_members_found_returns_empty() -> None:
  session = AsyncMock()
  session.execute.return_value = _result_with_rows([("u1",), ("u2",)])

  missing = await find_missing_org_members(session, organization_id="org-1", user_ids={"u1", "u2"})

  assert missing == set()


@pytest.mark.asyncio
async def test_unknown_user_is_reported_missing() -> None:
  session = AsyncMock()
  session.execute.return_value = _result_with_rows([("u1",)])

  missing = await find_missing_org_members(session, organization_id="org-1", user_ids={"u1", "intruso-de-outra-org"})

  assert missing == {"intruso-de-outra-org"}


@pytest.mark.asyncio
async def test_empty_input_skips_query() -> None:
  session = AsyncMock()

  missing = await find_missing_org_members(session, organization_id="org-1", user_ids=set())

  assert missing == set()
  session.execute.assert_not_awaited()
