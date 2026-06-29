from __future__ import annotations

from app.entities.network.schemas import ProviderCreate


def test_provider_create_ignores_client_verified_flag() -> None:
  """Mass assignment: o cliente não pode conceder o selo de verificado a si mesmo."""
  body = ProviderCreate(name="X", provider_type="Bordado", verified=True)  # type: ignore[call-arg]
  assert "verified" not in type(body).model_fields
  assert "verified" not in body.model_dump()
