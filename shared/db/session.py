from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from ..config import get_settings


def create_engine() -> AsyncEngine:
  settings = get_settings()
  return create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)


ENGINE = create_engine()
SESSIONMAKER = async_sessionmaker(ENGINE, expire_on_commit=False, class_=AsyncSession)


async def get_db_session() -> AsyncIterator[AsyncSession]:
  async with SESSIONMAKER() as session:
    yield session
