"""Планировщик: синхронизация трафика, автоотключение, уведомления."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.config import settings
from app.context import get_remnawave
from app.db.engine import session_scope
from app.db.models import NotificationLog, Subscription, User
from app.services.notifications import notify_expiry, notify_traffic
from app.services.settings import is_notifications_enabled


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _notified_recently(
    session, user_id: int, type_: str, within_hours: int
) -> bool:
    cutoff = _utcnow() - timedelta(hours=within_hours)
    row = (
        await session.execute(
            select(NotificationLog.id)
            .where(
                NotificationLog.user_id == user_id,
                NotificationLog.type == type_,
                NotificationLog.sent_at >= cutoff,
            )
            .limit(1)
        )
    ).first()
    return row is not None


async def sync_subscriptions() -> None:
    """Обновить трафик и автоотключить истёкшие подписки."""
    client = get_remnawave()
    now = _utcnow()
    async with session_scope() as session:
        subs = (
            (
                await session.execute(
                    select(Subscription).where(Subscription.status == "active")
                )
            )
            .scalars()
            .all()
        )
        for sub in subs:
            try:
                data = await client.get_user(sub.remnawave_short_uuid)
                used = int(
                    data.get("usedTrafficBytes")
                    or data.get("used_traffic_bytes")
                    or data.get("usedTraffic")
                    or 0
                )
                sub.traffic_used_bytes = used
                if sub.expires_at and sub.expires_at < now:
                    sub.status = "expired"
                    await client.disable_user(sub.remnawave_short_uuid)
            except Exception:  # noqa: BLE001
                continue


async def check_notifications(bot: Bot) -> None:
    """Отправить уведомления об истечении и расходе трафика."""
    now = _utcnow()
    async with session_scope() as session:
        if not await is_notifications_enabled(session):
            return
        subs = (
            (
                await session.execute(
                    select(Subscription).where(Subscription.status == "active")
                )
            )
            .scalars()
            .all()
        )
        for sub in subs:
            user = await session.get(User, sub.user_id)
            if user is None:
                continue

            if sub.traffic_limit_bytes > 0:
                pct = int(
                    sub.traffic_used_bytes * 100 / sub.traffic_limit_bytes
                )
                if pct >= settings.notify_traffic_percent and not await _notified_recently(
                    session, user.id, "traffic", 48
                ):
                    try:
                        await notify_traffic(session, bot, user, sub, pct)
                    except Exception:  # noqa: BLE001
                        continue

            if sub.expires_at:
                days_left = (sub.expires_at - now).days
                if days_left in settings.notify_before_days and not await _notified_recently(
                    session, user.id, "expiry", 24
                ):
                    try:
                        await notify_expiry(session, bot, user, sub, days_left)
                    except Exception:  # noqa: BLE001
                        continue


def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        sync_subscriptions,
        "interval",
        minutes=30,
        id="sync_subscriptions",
        replace_existing=True,
    )
    scheduler.add_job(
        check_notifications,
        "cron",
        hour=10,
        minute=0,
        args=[bot],
        id="check_notifications",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
