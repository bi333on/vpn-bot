"""Отправка конфига подписки (текст + QR)."""
from __future__ import annotations

from aiogram import Bot
from aiogram.types import BufferedInputFile

from app.db.models import Subscription, User
from app.services.qr import make_qr_png
from app.utils import fmt_bytes


async def send_subscription_config(
    bot: Bot, user: User, sub: Subscription
) -> None:
    lines = [
        "✅ <b>Подписка активирована!</b>",
        "",
        f"Трафик: <b>{fmt_bytes(sub.traffic_limit_bytes)}</b>",
        f"Устройства: <b>{sub.devices_limit}</b>",
    ]
    if sub.expires_at:
        lines.append(f"Действует до: <b>{sub.expires_at.strftime('%d.%m.%Y')}</b>")
    text = "\n".join(lines)

    await bot.send_message(user.telegram_id, text, parse_mode="HTML")
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
            caption="Отсканируйте QR в клиенте (v2rayNG, Streisand, Nekoray и др.)",
        )
    else:
        await bot.send_message(
            user.telegram_id,
            "⚠️ Не удалось сформировать ссылку. Обратитесь в поддержку.",
        )
