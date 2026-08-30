"""Кастомные эмодзи Telegram: шаблон {{emoji:ID}} в текстах сообщений.

Telegram рендерит премиум-эмодзи только в тексте сообщений (через <tg-emoji>).
В кнопках они не работают — там используется обычная версия эмодзи.
"""
from __future__ import annotations

import re

from app.db.engine import session_scope
from app.services.settings import get_setting, set_setting
from app.utils import tg_emoji

EMOJI_MAP_KEY = "emoji_map"

# Кэш ID->символ для синхронного применения в i18n.tr().
EMOJI_MAP: dict[str, str] = {}

_PLACEHOLDER = re.compile(r"\{\{emoji:(\d+)(?::([^}]*))?\}\}")


async def load_emoji_map() -> None:
    """Загрузить сохранённую карту ID->символ при старте."""
    async with session_scope() as session:
        data = await get_setting(session, EMOJI_MAP_KEY, {})
    if isinstance(data, dict):
        EMOJI_MAP.clear()
        EMOJI_MAP.update({str(k): str(v) for k, v in data.items()})


async def remember_emoji(session, emoji_id: str, char: str) -> None:
    """Запомнить пару ID->символ (вызывается, когда админ шлёт custom-эмодзи)."""
    emoji_id = str(emoji_id)
    char = char or "🙂"
    EMOJI_MAP[emoji_id] = char
    await set_setting(session, EMOJI_MAP_KEY, dict(EMOJI_MAP))


def extract_custom_emoji(message) -> tuple[str | None, str | None]:
    """Достать custom-эмодзи (ID и символ) из сообщения, если оно есть."""
    text = message.text or message.caption or ""
    for ent in message.entities or []:
        if ent.type == "custom_emoji" and getattr(ent, "custom_emoji_id", None):
            char = text[ent.offset : ent.offset + ent.length] or "🙂"
            return str(ent.custom_emoji_id), char
    return None, None


def apply_custom_emojis(text: str) -> str:
    """Заменить {{emoji:ID}} и {{emoji:ID:символ}} на <tg-emoji>."""
    if not text or "{{emoji:" not in text:
        return text

    def _repl(match: re.Match) -> str:
        emoji_id = match.group(1)
        fallback = (match.group(2) or "").strip()
        if not fallback:
            fallback = EMOJI_MAP.get(emoji_id) or "🙂"
        return tg_emoji(emoji_id, fallback)

    return _PLACEHOLDER.sub(_repl, text)
