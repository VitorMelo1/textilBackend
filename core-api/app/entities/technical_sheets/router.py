from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import TechnicalSheet, TechnicalSheetStep, TechnicalSheetStepEnabled
from shared.db.session import get_db_session
from shared.security.jwt import TokenClaims
from shared.security.permissions import require_permission

from .constants import WORKFLOW_STEP_ORDER
from .schemas import StepState, TechnicalSheetCreate, TechnicalSheetOut, TechnicalSheetUpdate


router = APIRouter(prefix="/technical-sheets", tags=["technical_sheets"])
RequireFichas = Depends(require_permission("fichas"))


async def _sheet_out(session: AsyncSession, sheet: TechnicalSheet) -> TechnicalSheetOut:
  q_steps = await session.execute(select(TechnicalSheetStep).where(TechnicalSheetStep.sheet_id == sheet.id))
  steps = q_steps.scalars().all()
  q_enabled = await session.execute(
    select(TechnicalSheetStepEnabled).where(TechnicalSheetStepEnabled.sheet_id == sheet.id)
  )
  enabled_rows = q_enabled.scalars().all()

  enabled = {r.step_id: bool(r.enabled) for r in enabled_rows}
  progress: dict[str, StepState] = {}
  for st in steps:
    progress[st.step_id] = StepState(
      completed=bool(st.completed),
      date=st.completed_date,
      responsible=st.responsible,
    )

  # preencher defaults
  for step_id in WORKFLOW_STEP_ORDER:
    enabled.setdefault(step_id, True)
    progress.setdefault(step_id, StepState())

  sizes = json.loads(sheet.sizes_json or "{}")
  if not isinstance(sizes, dict):
    sizes = {}

  return TechnicalSheetOut(
    id=sheet.id,
    organization_id=sheet.organization_id,
    order_number=sheet.order_number,
    model_name=sheet.model_name,
    fabric=sheet.fabric,
    status=sheet.status,
    size_grade_type=sheet.size_grade_type,
    sizes={str(k): int(v) for k, v in sizes.items()},
    total_pieces=int(sheet.total_pieces),
    observations=sheet.observations,
    step_enabled=enabled,
    progress=progress,
    created_at=sheet.created_at,
  )


@router.get("", response_model=list[TechnicalSheetOut])
async def list_sheets(claims: TokenClaims = RequireFichas, session: AsyncSession = Depends(get_db_session)):
  q = await session.execute(
    select(TechnicalSheet)
    .where(TechnicalSheet.organization_id == claims.org)
    .order_by(TechnicalSheet.created_at.desc())
  )
  sheets = q.scalars().all()
  return [await _sheet_out(session, s) for s in sheets]


@router.post("", response_model=TechnicalSheetOut)
async def create_sheet(
  body: TechnicalSheetCreate,
  claims: TokenClaims = RequireFichas,
  session: AsyncSession = Depends(get_db_session),
):
  sizes = {str(k): int(v) for k, v in body.sizes.items() if int(v) > 0}
  total = sum(sizes.values())
  sheet = TechnicalSheet(
    organization_id=claims.org,
    order_number=body.order_number,
    model_name=body.model_name,
    fabric=body.fabric,
    status=body.status,
    size_grade_type=body.size_grade_type,
    sizes_json=json.dumps(sizes, ensure_ascii=False),
    total_pieces=total,
    observations=body.observations,
  )
  session.add(sheet)
  await session.flush()

  # defaults: steps + enabled
  for step_id in WORKFLOW_STEP_ORDER:
    session.add(TechnicalSheetStep(organization_id=claims.org, sheet_id=sheet.id, step_id=step_id, completed=False))
    session.add(TechnicalSheetStepEnabled(organization_id=claims.org, sheet_id=sheet.id, step_id=step_id, enabled=True))

  await session.commit()
  return await _sheet_out(session, sheet)


@router.get("/{sheet_id}", response_model=TechnicalSheetOut)
async def get_sheet(
  sheet_id: str, claims: TokenClaims = RequireFichas, session: AsyncSession = Depends(get_db_session)
):
  q = await session.execute(
    select(TechnicalSheet).where(TechnicalSheet.id == sheet_id, TechnicalSheet.organization_id == claims.org)
  )
  sheet = q.scalar_one_or_none()
  if sheet is None:
    raise HTTPException(status_code=404, detail="sheet not found")
  return await _sheet_out(session, sheet)


@router.patch("/{sheet_id}", response_model=TechnicalSheetOut)
async def update_sheet(
  sheet_id: str,
  body: TechnicalSheetUpdate,
  claims: TokenClaims = RequireFichas,
  session: AsyncSession = Depends(get_db_session),
):
  q = await session.execute(
    select(TechnicalSheet).where(TechnicalSheet.id == sheet_id, TechnicalSheet.organization_id == claims.org)
  )
  sheet = q.scalar_one_or_none()
  if sheet is None:
    raise HTTPException(status_code=404, detail="sheet not found")

  if body.fabric is not None:
    sheet.fabric = body.fabric
  if body.status is not None:
    sheet.status = body.status
  if body.observations is not None:
    sheet.observations = body.observations
  if body.size_grade_type is not None:
    sheet.size_grade_type = body.size_grade_type
  if body.sizes is not None:
    sizes = {str(k): int(v) for k, v in body.sizes.items() if int(v) > 0}
    sheet.sizes_json = json.dumps(sizes, ensure_ascii=False)
    sheet.total_pieces = sum(sizes.values())

  if body.progress is not None:
    for step_id, state in body.progress.items():
      q_step = await session.execute(
        select(TechnicalSheetStep).where(
          TechnicalSheetStep.sheet_id == sheet_id,
          TechnicalSheetStep.step_id == step_id,
        )
      )
      step = q_step.scalar_one_or_none()
      if step is None:
        step = TechnicalSheetStep(organization_id=claims.org, sheet_id=sheet_id, step_id=step_id, completed=False)
        session.add(step)
      step.completed = state.completed
      step.completed_date = state.date
      step.responsible = state.responsible

  if body.step_enabled is not None:
    for step_id, enabled in body.step_enabled.items():
      q_enabled = await session.execute(
        select(TechnicalSheetStepEnabled).where(
          TechnicalSheetStepEnabled.sheet_id == sheet_id,
          TechnicalSheetStepEnabled.step_id == step_id,
        )
      )
      row = q_enabled.scalar_one_or_none()
      if row is None:
        row = TechnicalSheetStepEnabled(organization_id=claims.org, sheet_id=sheet_id, step_id=step_id, enabled=True)
        session.add(row)
      row.enabled = enabled

  await session.commit()
  return await _sheet_out(session, sheet)
