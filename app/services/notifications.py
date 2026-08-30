"""Отправка уведомлений пользователям (expiry/traffic/payment)."""
from __future__ import annotations

from aiogram import Bot

from app.db.models import NotificationLog, Subscription, User
from app.i18n import get_lang, tr
from app.utils import fmt_bytes, fmt_money


async def _log(session, user_id: int, type_: str, meta: dict | None = None) -> None:
    session.add(NotificationLog(user_id=user_id, type=type_, meta=meta))


async def notify_expiry(
    session,
    bot: Bot,
    user: User,
    sub: Subscription,
    days_left: int,
) -> None:
    await _log(session, user.id, "expiry", {"subscription_id": sub.id, "days_left": days_left})
    await bot.send_message(
        user.telegram_id, tr(get_lang(user), "notify_expiry", days=days_left)
    )


async def notify_traffic(
    session,
    bot: Bot,
    user: User,
    sub: Subscription,
    percent: int,
) -> None:
    await _log(session, user.id, "traffic", {"subscription_id": sub.id, "percent": percent})
    await bot.send_message(
        user.telegram_id,
        tr(
            get_lang(user),
            "notify_traffic",
            percent=percent,
            used=fmt_bytes(sub.traffic_used_bytes),
            limit=fmt_bytes(sub.traffic_limit_bytes),
        ),
    )


async def notify_payment_success(bot: Bot, user: User, paid: int) -> None:
    await bot.send_message(
        user.telegram_id,
        f"✅ Оплата на сумму {fmt_money(paid)} подтверждена.",
    )
