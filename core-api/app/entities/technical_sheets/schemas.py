from __future__ import annotations

from datetime import date as _date, datetime
from pydantic import BaseModel, Field


class StepState(BaseModel):
  completed: bool = False
  date: _date | None = None
  responsible: str | None = None


class TechnicalSheetCreate(BaseModel):
  order_number: str
  model_name: str
  fabric: str
  status: str = "pending"
  size_grade_type: str = Field(default="letter", pattern="^(letter|jeans)$")
  sizes: dict[str, int] = Field(default_factory=dict)
  observations: str | None = None


class TechnicalSheetUpdate(BaseModel):
  fabric: str | None = None
  status: str | None = None
  observations: str | None = None
  size_grade_type: str | None = Field(default=None, pattern="^(letter|jeans)$")
  sizes: dict[str, int] | None = None
  progress: dict[str, StepState] | None = None
  step_enabled: dict[str, bool] | None = None


class TechnicalSheetOut(BaseModel):
  id: str
  organization_id: str
  order_number: str
  model_name: str
  fabric: str
  status: str
  size_grade_type: str
  sizes: dict[str, int]
  total_pieces: int
  observations: str | None = None
  step_enabled: dict[str, bool]
  progress: dict[str, StepState]
  created_at: datetime
