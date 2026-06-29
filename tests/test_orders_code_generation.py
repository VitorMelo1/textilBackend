from __future__ import annotations

import re
from datetime import date

from app.entities.orders.service import generate_order_code


def test_generate_order_code_format() -> None:
  code = generate_order_code(today=date(2026, 6, 10))
  assert re.fullmatch(r"PED-20260610-[0-9A-F]{4}", code)


def test_generate_order_code_varies() -> None:
  codes = {generate_order_code() for _ in range(20)}
  assert len(codes) > 1
