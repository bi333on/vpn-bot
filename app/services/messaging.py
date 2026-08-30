"""Отправка конфига подписки (текст + QR)."""
from __future__ import annotations

from aiogram import Bot
from aiogram.types import BufferedInputFile

from app.db.models import Subscription, User
from app.i18n import get_lang, tr
from app.keyboards.inline import back_to_menu
from app.services.qr import make_qr_png
from app.utils import fmt_bytes


async def send_subscription_config(
    bot: Bot, user: User, sub: Subscription
) -> None:
    lang = get_lang(user)
    lines = [
        tr(lang, "config_activated"),
        "",
        tr(lang, "config_traffic", traffic=fmt_bytes(sub.traffic_limit_bytes)),
        tr(lang, "config_devices", devices=sub.devices_limit),
    ]
    if sub.expires_at:
        lines.append(
            tr(lang, "config_until", date=sub.expires_at.strftime("%d.%m.%Y"))
        )
    text = "\n".join(lines)

    await bot.send_message(
        user.telegram_id, text, parse_mode="HTML", reply_markup=back_to_menu(lang)
    )
    if sub.config_link:
        await bot.send_message(
            user.telegram_id,
            f"<code>{sub.config_link}</code>",
            parse_mode="HTML",
        )
        png = make_qr_png(sub.config_link)
        await bot.send_photo(
            user.telegram_id,
            BufferedInputFile(png, filename="vpn_qr.png"),
            caption=tr(lang, "config_scan"),
        )
    else:
        await bot.send_message(
            user.telegram_id,
            tr(lang, "config_unavailable"),
        )
