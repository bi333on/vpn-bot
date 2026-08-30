"""Настройки дизайна: эмодзи/тексты кнопок, конструктор кнопок, картинки.

Хранится в таблице settings под ключом 'design' (JSON).
"""
from __future__ import annotations

from app.i18n import tr
from app.services.settings import get_setting, set_setting

DESIGN_KEY = "design"

# (slot, default_emoji, label_key, callback)
BUTTON_SLOTS: list = [
    ("buy", "⊕", "cabinet_buy", "buy"),
    ("subs", "📱", "cabinet_subs", "subs"),
    ("trial", "🎁", "cabinet_trial", "trial"),
    ("balance", "💳", "cabinet_balance_btn", "balance"),
    ("referral", "👥", "cabinet_referral", "referral"),
    ("gift", "🎁", "cabinet_gift", "gift"),
    ("about", "👁️", "cabinet_about", "about"),
    ("admin", "👑", "cabinet_admin", "admin_panel"),
    ("lang", "🌐", "cabinet_lang", "lang"),
]

# Экраны, над которыми можно ставить картинку.
SCREENS = ["cabinet", "balance", "buy", "subs"]


def default_design() -> dict:
    return {"emoji": {}, "labels": {}, "buttons": [], "images": {}}


async def get_design(session) -> dict:
    design = await get_setting(session, DESIGN_KEY, None)
    if not isinstance(design, dict):
        return default_design()
    d = default_design()
    d.update(design)
    return d


async def save_design(session, design: dict) -> None:
    await set_setting(session, DESIGN_KEY, design)


def button_label(slot: str, lang: str, design: dict) -> tuple[str, str]:
    """Вернуть (текст_кнопки, callback) для слота.

    Inline-кнопки не поддерживают HTML-разметку, поэтому числовой custom-emoji ID
    не рендерится — вместо него оставляем обычный эмодзи слота.
    """
    for s in BUTTON_SLOTS:
        if s[0] == slot:
            _, default_emoji, label_key, callback = s
            emoji = default_emoji
            custom = (design.get("emoji") or {}).get(slot)
            if custom:
                custom = str(custom).strip()
                if custom and not custom.isdigit():
                    emoji = custom
            label = (design.get("labels") or {}).get(slot) or tr(lang, label_key)
            return f"{emoji} {label}", callback
    return slot, slot


def slot_emoji(slot: str, design: dict) -> str:
    """Текущий эмодзи слота (для отображения в админке)."""
    for s in BUTTON_SLOTS:
        if s[0] == slot:
            return (design.get("emoji") or {}).get(slot) or s[1]
    return ""
