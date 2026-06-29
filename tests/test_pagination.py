from __future__ import annotations

from shared.api.pagination import PaginationParams


def test_pagination_defaults() -> None:
  p = PaginationParams()
  assert p.page == 1
  assert p.page_size == 20
  assert p.offset == 0
  assert p.limit == 20


def test_pagination_offset_and_limit() -> None:
  p = PaginationParams(page=3, page_size=10)
  assert p.offset == 20
  assert p.limit == 10
