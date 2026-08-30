"""Чтение/запись runtime-настроек (таблица settings, JSON)."""
from __future__ import annotations

import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Setting


async def get_setting(session: AsyncSession, key: str, default=None):
    row = await session.get(Setting, key)
    if row is None:
        return default
    try:
        return json.loads(row.value) if row.value else default
    except (TypeError, ValueError):
        return default if row.value in (None, "") else row.value


async def set_setting(session: AsyncSession, key: str, value) -> None:
    serialized = json.dumps(value, ensure_ascii=False)
    row = await session.get(Setting, key)
    if row is None:
        session.add(Setting(key=key, value=serialized))
    else:
        row.value = serialized


async def is_notifications_enabled(session: AsyncSession) -> bool:
    return bool(await get_setting(session, "notifications_enabled", True))
