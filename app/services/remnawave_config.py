"""Конфигурация Remnawave из БД (api-токен, uuid ноды), с fallback на env."""
from __future__ import annotations

from app.config import settings
from app.db.engine import session_scope
from app.services.settings import get_setting, set_setting

REMNAWAVE_TOKEN_KEY = "remnawave_api_token"
REMNAWAVE_NODE_KEY = "remnawave_node_uuid"


async def get_remnawave_api_token(session) -> str | None:
    token = await get_setting(session, REMNAWAVE_TOKEN_KEY, None)
    return str(token) if token else (settings.remnawave_api_token or None)


async def set_remnawave_api_token(session, token: str) -> None:
    await set_setting(session, REMNAWAVE_TOKEN_KEY, (token or "").strip())


async def get_remnawave_node_uuid(session) -> str | None:
    value = await get_setting(session, REMNAWAVE_NODE_KEY, None)
    return str(value) if value else (settings.remnawave_node_uuid or None)


async def set_remnawave_node_uuid(session, node_uuid: str) -> None:
    await set_setting(session, REMNAWAVE_NODE_KEY, (node_uuid or "").strip())


async def load_remnawave_settings() -> None:
    """Применить сохранённые токен и uuid ноды к клиенту (при старте)."""
    from app.context import get_remnawave

    async with session_scope() as session:
        token = await get_remnawave_api_token(session)
        node_uuid = await get_remnawave_node_uuid(session)
    client = get_remnawave()
    client.set_api_token(token)
    client.set_node_uuid(node_uuid)
