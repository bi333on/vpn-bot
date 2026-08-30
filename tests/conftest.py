"""Фикстуры тестов. Env-переменные задаются ДО импорта app."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("BOT_TOKEN", "123456:TEST")
os.environ.setdefault("ADMIN_IDS", "1")
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_bot.db"
os.environ["POLLING_MODE"] = "true"

import pytest_asyncio  # noqa: E402


@pytest_asyncio.fixture
async def db_session():
    from app.db import models
    from app.db.engine import SessionFactory, engine, init_db

    await init_db()
    async with SessionFactory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.drop_all)
