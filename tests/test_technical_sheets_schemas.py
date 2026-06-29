"""
Testes para schemas do módulo technical_sheets — sem asyncpg.
"""

from __future__ import annotations

from datetime import date as _date

import pytest

from app.entities.technical_sheets.schemas import StepState, TechnicalSheetUpdate


def test_update_schema_all_optional() -> None:
  """TechnicalSheetUpdate aceita body vazio — todos os campos são opcionais."""
  u = TechnicalSheetUpdate()
  assert u.fabric is None
  assert u.status is None
  assert u.observations is None
  assert u.size_grade_type is None
  assert u.sizes is None
  assert u.progress is None
  assert u.step_enabled is None


def test_update_schema_size_grade_type_validation() -> None:
  """size_grade_type só aceita 'letter' ou 'jeans'."""
  from pydantic import ValidationError

  with pytest.raises(ValidationError):
    TechnicalSheetUpdate(size_grade_type="invalid")

  assert TechnicalSheetUpdate(size_grade_type="letter").size_grade_type == "letter"
  assert TechnicalSheetUpdate(size_grade_type="jeans").size_grade_type == "jeans"


def test_update_schema_progress_uses_step_state() -> None:
  """Campo progress mapeia step_id → StepState."""
  u = TechnicalSheetUpdate(
    progress={
      "modeling": StepState(completed=True, date=_date(2024, 6, 1), responsible="Ana"),
      "cutting": StepState(completed=False),
    }
  )
  assert u.progress is not None
  assert u.progress["modeling"].completed is True
  assert u.progress["modeling"].responsible == "Ana"
  assert u.progress["cutting"].completed is False


def test_update_schema_step_enabled() -> None:
  """step_enabled mapeia step_id → bool."""
  u = TechnicalSheetUpdate(step_enabled={"modeling": True, "embroidery": False})
  assert u.step_enabled is not None
  assert u.step_enabled["embroidery"] is False
