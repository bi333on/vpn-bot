"""Асинхронный движок БД (SQLAlchemy 2.0 + aiosqlite)."""
from __future__ import annotations

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False, future=True)
SessionFactory = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


async def init_db() -> None:
    """Создать все таблицы (idempotent)."""
    from app.db import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)


@asynccontextmanager
async def session_scope():
    """Контекстный менеджер сессии с автоматическим commit/rollback."""
    async with SessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    await engine.dispose()
