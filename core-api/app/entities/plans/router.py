from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import get_settings
from shared.db.models import Plan, Subscription
from shared.db.session import get_db_session
from shared.security.deps import require_auth_claims

from .schemas import (
  BillingCheckoutRequest,
  BillingCheckoutResponse,
  BillingPortalRequest,
  BillingPortalResponse,
  PlanOut,
  SubscriptionOut,
  UpdateSubscriptionRequest,
)

try:
  import stripe
except Exception:  # pragma: no cover
  stripe = None  # type: ignore[assignment]

router = APIRouter(tags=["plans"])
DEFAULT_PLANS: tuple[tuple[str, str], ...] = (
  ("basic", "Plano Básico"),
  ("professional", "Plano Professional"),
  ("enterprise", "Plano Enterprise"),
)


@router.get("/plans", response_model=list[PlanOut])
async def list_plans(session: AsyncSession = Depends(get_db_session)):
  await _ensure_default_plans(session)
  q = await session.execute(select(Plan).order_by(Plan.key.asc()))
  rows = q.scalars().all()
  return [PlanOut(id=p.id, key=p.key, name=p.name) for p in rows]


async def _ensure_default_plans(session: AsyncSession) -> None:
  q = await session.execute(select(Plan))
  existing = q.scalars().all()
  existing_keys = {plan.key for plan in existing}
  changed = False
  for key, name in DEFAULT_PLANS:
    if key not in existing_keys:
      session.add(Plan(key=key, name=name))
      changed = True
  if changed:
    await session.flush()
    await session.commit()


async def _get_plan_by_key(session: AsyncSession, plan_key: str) -> Plan:
  q = await session.execute(select(Plan).where(Plan.key == plan_key))
  plan = q.scalar_one_or_none()
  if plan is None:
    raise HTTPException(status_code=404, detail="plan not found")
  return plan


async def _get_subscription_for_org(session: AsyncSession, organization_id: str) -> Subscription | None:
  q = await session.execute(select(Subscription).where(Subscription.organization_id == organization_id))
  return q.scalar_one_or_none()


async def _upsert_subscription(
  session: AsyncSession,
  *,
  organization_id: str,
  plan: Plan,
  status: str = "active",
  trial_days: int | None = None,
  trial_ends_at: datetime | None = None,
  stripe_customer_id: str | None = None,
  stripe_subscription_id: str | None = None,
) -> Subscription:
  sub = await _get_subscription_for_org(session, organization_id)
  resolved_trial_ends = trial_ends_at
  if trial_days:
    resolved_trial_ends = datetime.now(timezone.utc) + timedelta(days=trial_days)
  if sub is None:
    sub = Subscription(
      organization_id=organization_id,
      plan_id=plan.id,
      status=status,
      trial_ends_at=resolved_trial_ends,
      stripe_customer_id=stripe_customer_id,
      stripe_subscription_id=stripe_subscription_id,
    )
    session.add(sub)
  else:
    sub.plan_id = plan.id
    sub.status = status
    sub.trial_ends_at = resolved_trial_ends
    if stripe_customer_id:
      sub.stripe_customer_id = stripe_customer_id
    if stripe_subscription_id:
      sub.stripe_subscription_id = stripe_subscription_id
  await session.flush()
  return sub


async def _get_subscription_by_stripe_subscription_id(
  session: AsyncSession, stripe_subscription_id: str
) -> Subscription | None:
  q = await session.execute(select(Subscription).where(Subscription.stripe_subscription_id == stripe_subscription_id))
  return q.scalar_one_or_none()


async def _get_subscription_by_stripe_customer_id(
  session: AsyncSession, stripe_customer_id: str
) -> Subscription | None:
  q = await session.execute(select(Subscription).where(Subscription.stripe_customer_id == stripe_customer_id))
  return q.scalar_one_or_none()


async def _to_subscription_out(session: AsyncSession, sub: Subscription) -> SubscriptionOut:
  q = await session.execute(select(Plan).where(Plan.id == sub.plan_id))
  plan = q.scalar_one_or_none()
  return SubscriptionOut(
    id=sub.id,
    organization_id=sub.organization_id,
    plan_id=sub.plan_id,
    plan_key=(plan.key if plan else None),
    status=sub.status,
    trial_ends_at=sub.trial_ends_at,
  )


@router.get("/subscription/current", response_model=SubscriptionOut)
async def get_current_subscription(
  claims=Depends(require_auth_claims), session: AsyncSession = Depends(get_db_session)
):
  sub = await _get_subscription_for_org(session, claims.org)
  if sub is None:
    raise HTTPException(status_code=404, detail="subscription not found")
  return await _to_subscription_out(session, sub)


def _require_stripe():
  settings = get_settings()
  if stripe is None:
    raise HTTPException(status_code=500, detail="stripe package not installed")
  if not settings.STRIPE_SECRET_KEY:
    raise HTTPException(status_code=503, detail="stripe not configured")
  stripe.api_key = settings.STRIPE_SECRET_KEY
  return settings


def _price_map(settings) -> dict[str, str | None]:
  return {
    "basic": settings.STRIPE_PRICE_BASIC,
    "professional": settings.STRIPE_PRICE_PROFESSIONAL,
    "enterprise": settings.STRIPE_PRICE_ENTERPRISE,
  }


def _plan_key_from_price_id(settings, price_id: str | None) -> str | None:
  if not price_id:
    return None
  for plan_key, configured_price in _price_map(settings).items():
    if configured_price and configured_price == price_id:
      return plan_key
  return None


def _plan_key_from_subscription_obj(settings, subscription_obj: dict) -> str | None:
  metadata = subscription_obj.get("metadata") or {}
  if metadata.get("plan_key"):
    return metadata["plan_key"]
  items = subscription_obj.get("items", {}).get("data", [])
  if not items:
    return None
  price_id = items[0].get("price", {}).get("id")
  return _plan_key_from_price_id(settings, price_id)


def _unix_to_datetime(value: int | None) -> datetime | None:
  if not value:
    return None
  return datetime.fromtimestamp(value, tz=timezone.utc)


async def _persist_from_stripe_snapshot(
  session: AsyncSession,
  *,
  organization_id: str,
  plan_key: str,
  status: str,
  stripe_customer_id: str | None,
  stripe_subscription_id: str | None,
  trial_ends_at: datetime | None,
) -> Subscription:
  plan = await _get_plan_by_key(session, plan_key)
  return await _upsert_subscription(
    session,
    organization_id=organization_id,
    plan=plan,
    status=status,
    trial_ends_at=trial_ends_at,
    stripe_customer_id=stripe_customer_id,
    stripe_subscription_id=stripe_subscription_id,
  )


@router.post("/billing/checkout-session", response_model=BillingCheckoutResponse)
async def create_checkout_session(
  body: BillingCheckoutRequest,
  claims=Depends(require_auth_claims),
  session: AsyncSession = Depends(get_db_session),
):
  await _ensure_default_plans(session)
  await _get_plan_by_key(session, body.plan_key)
  settings = _require_stripe()
  price_id = _price_map(settings).get(body.plan_key)
  if not price_id:
    raise HTTPException(status_code=503, detail=f"stripe price not configured for {body.plan_key}")

  sub = await _get_subscription_for_org(session, claims.org)
  checkout_kwargs: dict[str, object] = {}
  if sub and sub.stripe_customer_id:
    checkout_kwargs["customer"] = sub.stripe_customer_id

  checkout = stripe.checkout.Session.create(
    mode="subscription",
    payment_method_types=["card"],
    line_items=[{"price": price_id, "quantity": 1}],
    success_url=body.success_url,
    cancel_url=body.cancel_url,
    client_reference_id=claims.org,
    metadata={"organization_id": claims.org, "plan_key": body.plan_key},
    subscription_data={
      "metadata": {"organization_id": claims.org, "plan_key": body.plan_key},
      **({"trial_period_days": body.trial_days} if body.trial_days else {}),
    },
    **checkout_kwargs,
  )
  return BillingCheckoutResponse(checkout_url=str(checkout.url))


@router.post("/billing/portal-session", response_model=BillingPortalResponse)
async def create_portal_session(
  body: BillingPortalRequest,
  claims=Depends(require_auth_claims),
  session: AsyncSession = Depends(get_db_session),
):
  _require_stripe()
  sub = await _get_subscription_for_org(session, claims.org)
  if not sub or not sub.stripe_customer_id:
    raise HTTPException(status_code=400, detail="no stripe customer for organization")
  try:
    portal = stripe.billing_portal.Session.create(
      customer=sub.stripe_customer_id,
      return_url=body.return_url,
    )
  except Exception as exc:
    raise HTTPException(status_code=400, detail=f"unable to create portal session: {exc}") from exc
  return BillingPortalResponse(portal_url=str(portal.url))


@router.post("/billing/webhook")
async def stripe_webhook(
  request: Request,
  stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
  session: AsyncSession = Depends(get_db_session),
):
  await _ensure_default_plans(session)
  settings = _require_stripe()
  raw = await request.body()
  if not settings.STRIPE_WEBHOOK_SECRET:
    raise HTTPException(status_code=503, detail="stripe webhook secret not configured")
  try:
    event = stripe.Webhook.construct_event(raw, stripe_signature, settings.STRIPE_WEBHOOK_SECRET)
  except Exception as exc:
    raise HTTPException(status_code=400, detail=f"invalid stripe webhook: {exc}") from exc

  event_type = event.get("type")
  data = event.get("data", {}).get("object", {})
  metadata = data.get("metadata") or {}
  organization_id = metadata.get("organization_id")
  plan_key = metadata.get("plan_key")

  if event_type == "checkout.session.completed":
    stripe_customer_id = data.get("customer")
    stripe_subscription_id = data.get("subscription")
    stripe_sub = None
    if stripe_subscription_id:
      stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)
      plan_key = plan_key or _plan_key_from_subscription_obj(settings, stripe_sub)
    if organization_id and plan_key:
      await _persist_from_stripe_snapshot(
        session,
        organization_id=organization_id,
        plan_key=plan_key,
        status=(stripe_sub.get("status") if stripe_sub else "active"),
        stripe_customer_id=str(stripe_customer_id) if stripe_customer_id else None,
        stripe_subscription_id=str(stripe_subscription_id) if stripe_subscription_id else None,
        trial_ends_at=_unix_to_datetime(stripe_sub.get("trial_end")) if stripe_sub else None,
      )

  if event_type in {"customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"}:
    stripe_subscription_id = data.get("id")
    stripe_customer_id = data.get("customer")
    status = data.get("status", "active")

    if not organization_id and stripe_subscription_id:
      existing = await _get_subscription_by_stripe_subscription_id(session, str(stripe_subscription_id))
      if existing:
        organization_id = existing.organization_id
    if not organization_id and stripe_customer_id:
      existing = await _get_subscription_by_stripe_customer_id(session, str(stripe_customer_id))
      if existing:
        organization_id = existing.organization_id

    plan_key = plan_key or _plan_key_from_subscription_obj(settings, data)
    if event_type == "customer.subscription.deleted":
      status = "cancelled"
    if organization_id and plan_key:
      await _persist_from_stripe_snapshot(
        session,
        organization_id=organization_id,
        plan_key=plan_key,
        status=status,
        stripe_customer_id=str(stripe_customer_id) if stripe_customer_id else None,
        stripe_subscription_id=str(stripe_subscription_id) if stripe_subscription_id else None,
        trial_ends_at=_unix_to_datetime(data.get("trial_end")),
      )

  await session.commit()
  return {"received": True}


@router.post("/subscription/current", response_model=SubscriptionOut)
async def update_current_subscription(
  body: UpdateSubscriptionRequest,
  claims=Depends(require_auth_claims),
  session: AsyncSession = Depends(get_db_session),
):
  await _ensure_default_plans(session)
  plan = await _get_plan_by_key(session, body.plan_key)
  current = await _get_subscription_for_org(session, claims.org)

  if body.plan_key == "basic":
    sub = await _upsert_subscription(
      session,
      organization_id=claims.org,
      plan=plan,
      status="active",
      trial_days=body.trial_days,
      stripe_customer_id=(current.stripe_customer_id if current else None),
      stripe_subscription_id=(current.stripe_subscription_id if current else None),
    )
    await session.commit()
    return await _to_subscription_out(session, sub)

  settings = _require_stripe()
  if not current or not current.stripe_subscription_id:
    raise HTTPException(
      status_code=409,
      detail="no active stripe subscription to change; create checkout first",
    )

  price_id = _price_map(settings).get(body.plan_key)
  if not price_id:
    raise HTTPException(status_code=503, detail=f"stripe price not configured for {body.plan_key}")

  try:
    stripe_sub = stripe.Subscription.retrieve(current.stripe_subscription_id)
    items = stripe_sub.get("items", {}).get("data", [])
    if not items:
      raise HTTPException(status_code=400, detail="stripe subscription has no billable items")
    changed = stripe.Subscription.modify(
      current.stripe_subscription_id,
      items=[{"id": items[0]["id"], "price": price_id}],
      metadata={"organization_id": claims.org, "plan_key": body.plan_key},
      proration_behavior="create_prorations",
    )
  except HTTPException:
    raise
  except Exception as exc:
    raise HTTPException(status_code=400, detail=f"unable to change stripe subscription: {exc}") from exc

  sub = await _upsert_subscription(
    session,
    organization_id=claims.org,
    plan=plan,
    status=changed.get("status", current.status),
    trial_ends_at=_unix_to_datetime(changed.get("trial_end")),
    stripe_customer_id=str(changed.get("customer")) if changed.get("customer") else current.stripe_customer_id,
    stripe_subscription_id=current.stripe_subscription_id,
  )
  await session.commit()
  return await _to_subscription_out(session, sub)


@router.post("/subscription/cancel", response_model=SubscriptionOut)
async def cancel_current_subscription(
  claims=Depends(require_auth_claims), session: AsyncSession = Depends(get_db_session)
):
  sub = await _get_subscription_for_org(session, claims.org)
  if sub is None:
    raise HTTPException(status_code=404, detail="subscription not found")

  if sub.stripe_subscription_id:
    _require_stripe()
    try:
      stripe_sub = stripe.Subscription.modify(sub.stripe_subscription_id, cancel_at_period_end=True)
      sub.status = (
        "cancel_at_period_end" if stripe_sub.get("cancel_at_period_end") else stripe_sub.get("status", "active")
      )
    except Exception as exc:
      raise HTTPException(status_code=400, detail=f"unable to cancel stripe subscription: {exc}") from exc
  else:
    sub.status = "cancelled"
  await session.flush()
  await session.commit()
  return await _to_subscription_out(session, sub)
