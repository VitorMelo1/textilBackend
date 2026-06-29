from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


InventoryCategory = Literal["tecido", "linha", "botao", "ziper", "outro"]
InventoryUnit = Literal["metro", "kg", "unidade", "rolo"]


class InventoryItemCreate(BaseModel):
  name: str = Field(max_length=240)
  category: InventoryCategory
  current_stock: float = Field(ge=0)
  min_stock: float = Field(ge=0)
  unit: InventoryUnit
  unit_cost: float = Field(ge=0)
  supplier: str | None = Field(default=None, max_length=240)


class InventoryItemUpdate(BaseModel):
  name: str | None = Field(default=None, max_length=240)
  category: InventoryCategory | None = None
  min_stock: float | None = Field(default=None, ge=0)
  unit: InventoryUnit | None = None
  unit_cost: float | None = Field(default=None, ge=0)
  supplier: str | None = Field(default=None, max_length=240)


class InventoryItemOut(BaseModel):
  id: str
  organization_id: str
  name: str
  category: str
  current_stock: float
  min_stock: float
  unit: str
  unit_cost: float
  supplier: str | None = None
  is_below_min: bool
  created_at: datetime
  updated_at: datetime


class InventoryMovementCreate(BaseModel):
  movement_type: Literal["entrada", "saida"]
  quantity: float = Field(gt=0)
  reason: str = ""


class InventoryMovementOut(BaseModel):
  id: str
  organization_id: str
  item_id: str
  movement_type: str
  quantity: float
  reason: str
  recorded_by_user_id: str
  created_at: datetime


class InventoryMovementCreateResult(BaseModel):
  movement: InventoryMovementOut
  current_stock_after: float
