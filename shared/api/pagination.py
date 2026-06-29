from __future__ import annotations

from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field


DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

T = TypeVar("T")


class PaginationParams(BaseModel):
  page: int = Field(default=DEFAULT_PAGE, ge=1)
  page_size: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)

  @property
  def offset(self) -> int:
    return (self.page - 1) * self.page_size

  @property
  def limit(self) -> int:
    return self.page_size


def pagination_params(
  page: int = Query(DEFAULT_PAGE, ge=1),
  page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> PaginationParams:
  return PaginationParams(page=page, page_size=page_size)


class PaginatedResponse(BaseModel, Generic[T]):
  items: list[T]
  total: int
  page: int
  page_size: int
