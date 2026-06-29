from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

pytest.importorskip("asyncpg")

from app.entities.plans.router import cancel_current_subscription, update_current_subscription
from app.entities.plans.schemas import SubscriptionOut, UpdateSubscriptionRequest


@pytest.mark.asyncio
async def test_update_current_subscription_basic_keeps_stripe_ids() -> None:
  session = AsyncMock()
  claims = type("Claims", (), {"org": "org-1"})()
  plan = type("Plan", (), {"id": "plan-basic", "key": "basic"})()
  current = type(
    "Subscription",
    (),
    {
      "stripe_customer_id": "cus_123",
      "stripe_subscription_id": "sub_123",
    },
  )()
  updated = type("Subscription", (), {"id": "sub-local"})()
  response = SubscriptionOut(
    id="sub-local",
    organization_id="org-1",
    plan_id="plan-basic",
    plan_key="basic",
    status="active",
    trial_ends_at=None,
  )

  with (
    patch("app.entities.plans.router._ensure_default_plans", new=AsyncMock()),
    patch("app.entities.plans.router._get_plan_by_key", new=AsyncMock(return_value=plan)),
    patch("app.entities.plans.router._get_subscription_for_org", new=AsyncMock(return_value=current)),
    patch("app.entities.plans.router._to_subscription_out", new=AsyncMock(return_value=response)),
    patch("app.entities.plans.router._upsert_subscription", new=AsyncMock(return_value=updated)) as upsert_mock,
  ):
    result = await update_current_subscription(
      UpdateSubscriptionRequest(plan_key="basic", trial_days=14),
      claims=claims,
      session=session,
    )

  assert result.plan_key == "basic"
  upsert_mock.assert_awaited_once()
  assert upsert_mock.await_args.kwargs["stripe_customer_id"] == "cus_123"
  assert upsert_mock.await_args.kwargs["stripe_subscription_id"] == "sub_123"


@pytest.mark.asyncio
async def test_update_current_subscription_paid_plan_requires_checkout_first() -> None:
  session = AsyncMock()
  claims = type("Claims", (), {"org": "org-1"})()
  plan = type("Plan", (), {"id": "plan-pro", "key": "professional"})()

  with (
    patch("app.entities.plans.router._ensure_default_plans", new=AsyncMock()),
    patch("app.entities.plans.router._get_plan_by_key", new=AsyncMock(return_value=plan)),
    patch("app.entities.plans.router._get_subscription_for_org", new=AsyncMock(return_value=None)),
    patch("app.entities.plans.router._require_stripe") as require_stripe_mock,
  ):
    with pytest.raises(HTTPException) as exc:
      await update_current_subscription(
        UpdateSubscriptionRequest(plan_key="professional"),
        claims=claims,
        session=session,
      )

  assert exc.value.status_code == 409
  assert exc.value.detail == "no active stripe subscription to change; create checkout first"
  require_stripe_mock.assert_not_called()


@pytest.mark.asyncio
async def test_cancel_current_subscription_without_stripe_marks_cancelled() -> None:
  session = AsyncMock()
  claims = type("Claims", (), {"org": "org-1"})()
  local_sub = type(
    "Subscription",
    (),
    {
      "stripe_subscription_id": None,
      "status": "active",
    },
  )()
  response = SubscriptionOut(
    id="sub-local",
    organization_id="org-1",
    plan_id="plan-basic",
    plan_key="basic",
    status="cancelled",
    trial_ends_at=None,
  )

  with (
    patch("app.entities.plans.router._get_subscription_for_org", new=AsyncMock(return_value=local_sub)),
    patch("app.entities.plans.router._to_subscription_out", new=AsyncMock(return_value=response)),
  ):
    result = await cancel_current_subscription(claims=claims, session=session)

  assert local_sub.status == "cancelled"
  assert result.status == "cancelled"
