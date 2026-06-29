from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.entities.interest_requests.service import validate_status_transition


def test_validate_status_transition_pending_to_matched() -> None:
  validate_status_transition("pending", "matched")


def test_validate_status_transition_pending_to_rejected() -> None:
  validate_status_transition("pending", "rejected")


def test_validate_status_transition_invalid_from_matched() -> None:
  with pytest.raises(HTTPException) as exc:
    validate_status_transition("matched", "rejected")
  assert exc.value.status_code == 422


def test_validate_status_transition_invalid_from_rejected() -> None:
  with pytest.raises(HTTPException) as exc:
    validate_status_transition("rejected", "matched")
  assert exc.value.status_code == 422
