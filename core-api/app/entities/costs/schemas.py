from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CostCalculationCreate(BaseModel):
  product_name: str = Field(max_length=240)
  quantity: int = Field(gt=0)
  profit_margin: float = Field(default=0, ge=0)


class CostCalculationUpdate(BaseModel):
  product_name: str | None = Field(default=None, max_length=240)
  quantity: int | None = Field(default=None, gt=0)
  profit_margin: float | None = Field(default=None, ge=0)


class CostCalculationOut(BaseModel):
  id: str
  organization_id: str
  product_name: str
  quantity: int
  total_material_cost: float
  total_labor_cost: float
  total_cost: float
  cost_per_unit: float
  profit_margin: float
  suggested_price: float
  created_at: datetime
  updated_at: datetime


class CostCalculationMaterialCreate(BaseModel):
  name: str = Field(max_length=240)
  quantity: float = Field(ge=0)
  unit: str = Field(default="", max_length=40)
  unit_cost: float = Field(ge=0)
  sort_order: int = 0


class CostCalculationMaterialUpdate(BaseModel):
  name: str | None = Field(default=None, max_length=240)
  quantity: float | None = Field(default=None, ge=0)
  unit: str | None = Field(default=None, max_length=40)
  unit_cost: float | None = Field(default=None, ge=0)
  sort_order: int | None = None


class CostCalculationMaterialOut(BaseModel):
  id: str
  organization_id: str
  calculation_id: str
  name: str
  quantity: float
  unit: str
  unit_cost: float
  total_cost: float
  sort_order: int
  created_at: datetime
  updated_at: datetime


class CostCalculationLaborCreate(BaseModel):
  description: str = Field(max_length=240)
  hours: float = Field(ge=0)
  hourly_rate: float = Field(ge=0)
  sort_order: int = 0


class CostCalculationLaborUpdate(BaseModel):
  description: str | None = Field(default=None, max_length=240)
  hours: float | None = Field(default=None, ge=0)
  hourly_rate: float | None = Field(default=None, ge=0)
  sort_order: int | None = None


class CostCalculationLaborOut(BaseModel):
  id: str
  organization_id: str
  calculation_id: str
  description: str
  hours: float
  hourly_rate: float
  total_cost: float
  sort_order: int
  created_at: datetime
  updated_at: datetime
