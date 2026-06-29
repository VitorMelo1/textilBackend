from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


OrderPriority = Literal["high", "medium", "low"]
OrderStage = Literal["planejamento", "corte", "costura", "bordado", "acabamento", "conferencia", "expedicao"]


class OrderCreate(BaseModel):
  # Quando omitido, o backend gera o código (IDs de negócio não vêm do cliente).
  order_code: str | None = Field(default=None, max_length=60)
  client_name: str = Field(max_length=240)
  product_name: str = Field(max_length=240)
  quantity: int = Field(ge=0)
  deadline: date
  priority: OrderPriority = "medium"
  notes: str | None = None
  stage: OrderStage = "planejamento"
  progress: int = Field(default=0, ge=0, le=100)
  unit_price: float = Field(default=0.0, ge=0)
  technical_sheet_id: str | None = None


class OrderUpdate(BaseModel):
  client_name: str | None = Field(default=None, max_length=240)
  product_name: str | None = Field(default=None, max_length=240)
  quantity: int | None = Field(default=None, ge=0)
  deadline: date | None = None
  priority: OrderPriority | None = None
  notes: str | None = None
  stage: OrderStage | None = None
  progress: int | None = Field(default=None, ge=0, le=100)
  unit_price: float | None = Field(default=None, ge=0)
  technical_sheet_id: str | None = None


class OrderOut(BaseModel):
  id: str
  organization_id: str
  order_code: str
  client_name: str
  product_name: str
  quantity: int
  deadline: date
  days_until_deadline: int
  priority: str
  notes: str | None = None
  stage: str
  progress: int
  unit_price: float = 0.0
  technical_sheet_id: str | None = None
  created_at: datetime
  updated_at: datetime


class OrderBatchCreate(BaseModel):
  lot_number: str = Field(max_length=60)
  quantity_sent: int = Field(ge=0)
  quantity_completed: int = Field(default=0, ge=0)
  status: Literal["pending", "in_progress", "completed"] = "pending"
  sent_date: date | None = None
  completed_date: date | None = None


class OrderBatchUpdate(BaseModel):
  lot_number: str | None = Field(default=None, max_length=60)
  quantity_sent: int | None = Field(default=None, ge=0)
  quantity_completed: int | None = Field(default=None, ge=0)
  status: Literal["pending", "in_progress", "completed"] | None = None
  sent_date: date | None = None
  completed_date: date | None = None


class OrderBatchOut(BaseModel):
  id: str
  organization_id: str
  order_id: str
  lot_number: str
  quantity_sent: int
  quantity_completed: int
  status: str
  sent_date: date | None = None
  completed_date: date | None = None
  created_at: datetime
  updated_at: datetime
