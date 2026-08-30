"""Настройки дизайна: эмодзи/тексты кнопок, конструктор кнопок, картинки.

Хранится в таблице settings под ключом 'design' (JSON).
"""
from __future__ import annotations

from functools import lru_cache
from io import BytesIO

from aiogram.types import BufferedInputFile

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


@lru_cache(maxsize=1)
def placeholder_image_bytes() -> bytes:
    """Сгенерировать PNG-баннер-заглушку для экранов (кэшируется)."""
    from PIL import Image, ImageDraw, ImageFont

    width, height = 1200, 400
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)
    top = (8, 14, 26)
    bottom = (22, 46, 72)
    for y in range(height):
        t = y / max(height - 1, 1)
        draw.line(
            [(0, y), (width, y)],
            fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)),
        )

    try:
        font_big = ImageFont.load_default(size=110)
        font_small = ImageFont.load_default(size=38)
    except TypeError:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()

    def _center(text, font, y, fill):
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        draw.text(((width - w) / 2, y), text, fill=fill, font=font)
        return h

    h1 = _center("VPN", font_big, 110, (255, 255, 255))
    _center("SECURE · FAST · ANONYMOUS", font_small, 110 + h1 + 16, (150, 178, 205))

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def answer_photo_caption(msg, image: str, text: str, kb) -> bool:
    """Отправить фото с подписью одним сообщением. Вернуть True при успехе."""
    try:
        await msg.answer_photo(
            photo=image, caption=text, parse_mode="HTML", reply_markup=kb
        )
        return True
    except Exception:  # noqa: BLE001
        return False


async def send_screen(
    msg, image: str, text: str, kb, placeholder: bool = False
) -> None:
    """Отправить экран одним сообщением: картинка сверху, текст — подпись."""
    if image and await answer_photo_caption(msg, image, text, kb):
        return
    if placeholder:
        photo = BufferedInputFile(placeholder_image_bytes(), filename="banner.png")
        await msg.answer_photo(
            photo=photo, caption=text, parse_mode="HTML", reply_markup=kb
        )
    else:
        await msg.answer(text, parse_mode="HTML", reply_markup=kb)


def patch_edit_text() -> None:
    """Сделать Message.edit_text совместимым с медиа-сообщениями.

    Кабинет отправляется как фото с подписью (caption). На таком сообщении
    Telegram отклоняет editMessageText — нужно editMessageCaption. Этот патч
    прозрачно маршрутизирует edit_text на edit_caption для фото/видео/документов.
    """
    from aiogram.types import Message

    original = Message.edit_text

    async def edit_text(self, text, **kwargs):
        is_media = bool(
            getattr(self, "photo", None)
            or getattr(self, "video", None)
            or getattr(self, "document", None)
            or getattr(self, "animation", None)
        )
        if is_media:
            caption_kwargs = {}
            for key in ("inline_message_id", "parse_mode", "reply_markup"):
                if key in kwargs:
                    caption_kwargs[key] = kwargs.pop(key)
            if "entities" in kwargs:
                caption_kwargs["caption_entities"] = kwargs.pop("entities")
            return await self.edit_caption(caption=text, **caption_kwargs)
        return await original(self, text, **kwargs)

    Message.edit_text = edit_text
