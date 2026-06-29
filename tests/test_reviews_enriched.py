"""
Testes para ReviewOut enriquecido com provider_name e created_at.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.entities.reviews.schemas import ReviewCreate, ReviewOut


# Argumentos mínimos válidos para ReviewOut (reutilizados em vários testes)
_REVIEW_OUT_BASE = dict(
  id="r1",
  organization_id="o",
  provider_id="p",
  author_user_id="u",
  rating=5,
  quality=5,
  deadline=5,
  communication=5,
)


# ---------------------------------------------------------------------------
# ReviewOut — novos campos opcionais
# ---------------------------------------------------------------------------


def test_review_out_provider_name_defaults_to_none() -> None:
  """ReviewOut sem provider_name deve ter provider_name=None."""
  review = ReviewOut(**_REVIEW_OUT_BASE)
  assert review.provider_name is None


def test_review_out_created_at_defaults_to_none() -> None:
  """ReviewOut sem created_at deve ter created_at=None."""
  review = ReviewOut(**_REVIEW_OUT_BASE)
  assert review.created_at is None


def test_review_out_accepts_provider_name() -> None:
  """ReviewOut com provider_name deve preservar o valor."""
  review = ReviewOut(**_REVIEW_OUT_BASE, provider_name="Empresa XPTO")
  assert review.provider_name == "Empresa XPTO"


def test_review_out_accepts_created_at_iso_string() -> None:
  """ReviewOut com created_at em string ISO deve preservar o valor."""
  review = ReviewOut(**_REVIEW_OUT_BASE, created_at="2026-06-09T10:00:00")
  assert review.created_at == "2026-06-09T10:00:00"


# ---------------------------------------------------------------------------
# ReviewCreate — validação de campos
# ---------------------------------------------------------------------------


def test_review_create_still_valid() -> None:
  """ReviewCreate com campos obrigatórios funciona sem erro."""
  review = ReviewCreate(
    provider_id="p",
    rating=4,
    quality=3,
    deadline=5,
    communication=4,
  )
  assert review.provider_id == "p"
  assert review.rating == 4


def test_review_create_rating_range() -> None:
  """ReviewCreate com rating=0 deve lançar ValidationError (ge=1)."""
  with pytest.raises(ValidationError):
    ReviewCreate(
      provider_id="p",
      rating=0,
      quality=3,
      deadline=5,
      communication=4,
    )
