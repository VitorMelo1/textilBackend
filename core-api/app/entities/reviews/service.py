from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.models import Provider, Review


async def refresh_provider_reputation(session: AsyncSession, provider: Provider) -> None:
  """Mantém rating médio e contagem do prestador consistentes com as reviews."""
  q = await session.execute(
    select(func.count(Review.id), func.avg(Review.rating)).where(Review.provider_id == provider.id)
  )
  review_count, average_rating = q.one()
  provider.review_count = int(review_count or 0)
  provider.rating = float(average_rating) if average_rating is not None else 0.0
