from __future__ import annotations

import ast
from pathlib import Path


from shared.security.permissions import has_permission, parse_permissions_csv


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _function_defaults(source_path: str, function_name: str) -> list[ast.expr]:
  tree = ast.parse((BACKEND_ROOT / source_path).read_text(encoding="utf-8"))
  for node in ast.walk(tree):
    if isinstance(node, ast.AsyncFunctionDef) and node.name == function_name:
      return list(node.args.defaults) + list(node.args.kw_defaults)
  raise AssertionError(f"{function_name} not found in {source_path}")


def _default_uses_name(defaults: list[ast.expr], name: str) -> bool:
  return any(isinstance(default, ast.Name) and default.id == name for default in defaults)


def test_parse_permissions_csv_empty() -> None:
  assert parse_permissions_csv("") == set()
  assert parse_permissions_csv("  ,  ") == set()


def test_parse_permissions_csv_values() -> None:
  assert parse_permissions_csv("pedidos, estoque,rede") == {"pedidos", "estoque", "rede"}


def test_has_permission_owner_bypasses() -> None:
  assert has_permission(role="owner", permissions_csv="", slug="rede") is True


def test_has_permission_member_with_slug() -> None:
  assert has_permission(role="member", permissions_csv="rede,chat", slug="rede") is True
  assert has_permission(role="member", permissions_csv="chat", slug="rede") is False


def test_has_permission_member_without_owner_role() -> None:
  assert has_permission(role="member", permissions_csv="", slug="pedidos") is False


def test_technical_sheets_routes_require_fichas_permission() -> None:
  source = "core-api/app/entities/technical_sheets/router.py"

  for endpoint in ("list_sheets", "create_sheet", "get_sheet", "update_sheet"):
    assert _default_uses_name(_function_defaults(source, endpoint), "RequireFichas")


def test_reviews_routes_require_rede_permission() -> None:
  source = "core-api/app/entities/reviews/router.py"

  for endpoint in ("list_reviews", "create_review"):
    assert _default_uses_name(_function_defaults(source, endpoint), "RequireRede")


def test_provider_creation_requires_owner_role() -> None:
  defaults = _function_defaults("core-api/app/entities/network/router.py", "create_provider")

  assert _default_uses_name(defaults, "RequireOwner")
