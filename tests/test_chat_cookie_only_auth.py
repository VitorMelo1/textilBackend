from __future__ import annotations

import ast
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
CHAT_ROUTER = BACKEND_ROOT / "chat-service/app/entities/chat/router.py"


def _tree() -> ast.Module:
  return ast.parse(CHAT_ROUTER.read_text(encoding="utf-8"))


def test_backfill_messages_does_not_accept_token_query_param() -> None:
  tree = _tree()
  for node in ast.walk(tree):
    if isinstance(node, ast.AsyncFunctionDef) and node.name == "backfill_messages":
      arg_names = [arg.arg for arg in node.args.args]
      assert "token" not in arg_names
      return
  raise AssertionError("backfill_messages endpoint not found")


def test_websocket_chat_does_not_read_query_params_token() -> None:
  tree = _tree()
  for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
      if node.func.attr == "get" and isinstance(node.func.value, ast.Attribute):
        assert node.func.value.attr != "query_params"


def test_backfill_messages_does_not_filter_messages_by_requester_org() -> None:
  source = CHAT_ROUTER.read_text(encoding="utf-8")
  assert "Message.organization_id == claims.org" not in source
