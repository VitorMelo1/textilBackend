from __future__ import annotations

import ast
from pathlib import Path


from shared.security.permissions import has_entitlement, has_permission, parse_permissions_csv


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


def test_profile_plan_entitlement_blocks_solo_operational_modules() -> None:
  assert has_entitlement(business_profile="solo", plan_key="basic", slug="pedidos") is True
  assert has_entitlement(business_profile="solo", plan_key="basic", slug="estoque") is False
  assert has_entitlement(business_profile="solo", plan_key="basic", slug="custos") is False


def test_company_profiles_can_access_inventory_and_costs_on_basic_plan() -> None:
  assert has_entitlement(business_profile="atelier", plan_key="basic", slug="estoque") is True
  assert has_entitlement(business_profile="atelier", plan_key="basic", slug="custos") is True
  assert has_entitlement(business_profile="industry", plan_key="basic", slug="estoque") is True
  assert has_entitlement(business_profile="industry", plan_key="basic", slug="custos") is True


def test_team_entitlement_is_enterprise_only_for_company_profiles() -> None:
  assert has_entitlement(business_profile="solo", plan_key="enterprise", slug="team") is False
  assert has_entitlement(business_profile="atelier", plan_key="professional", slug="team") is False
  assert has_entitlement(business_profile="atelier", plan_key="enterprise", slug="team") is True
  assert has_entitlement(business_profile="industry", plan_key="professional", slug="team") is False
  assert has_entitlement(business_profile="industry", plan_key="enterprise", slug="team") is True


def test_unknown_entitlement_slug_remains_role_permission_only() -> None:
  assert has_entitlement(business_profile=None, plan_key=None, slug="custom-admin-action") is True


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


def test_team_routes_require_owner_and_team_entitlement() -> None:
  source = "core-api/app/entities/team/router.py"
  source_text = (BACKEND_ROOT / source).read_text(encoding="utf-8")

  assert 'require_owner_entitled("team")' in source_text

  for endpoint in ("list_members", "update_member", "delete_member", "create_invite", "list_invites", "cancel_invite"):
    assert _default_uses_name(_function_defaults(source, endpoint), "RequireOwner")
