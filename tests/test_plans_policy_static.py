from __future__ import annotations

import ast
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PLANS_ROUTER = BACKEND_ROOT / "core-api/app/entities/plans/router.py"


def test_paid_plan_direct_update_rejects_before_requiring_stripe_configuration() -> None:
  tree = ast.parse(PLANS_ROUTER.read_text(encoding="utf-8"))
  for node in ast.walk(tree):
    if isinstance(node, ast.AsyncFunctionDef) and node.name == "update_current_subscription":
      stripe_call_line = next(
        child.lineno
        for child in ast.walk(node)
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == "_require_stripe"
      )
      no_current_check_line = next(
        child.lineno
        for child in ast.walk(node)
        if isinstance(child, ast.If) and "not current or not current.stripe_subscription_id" in ast.unparse(child.test)
      )
      assert no_current_check_line < stripe_call_line
      return
  raise AssertionError("update_current_subscription not found")
