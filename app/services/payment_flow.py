"""Завершение платежа: создание подписки, списание баланса, рефералка."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.context import get_remnawave
from app.db.models import Payment, Plan, Subscription, User
from app.services.balance import add_balance, spend_balance
from app.services.promo import mark_promo_used, validate_promo
from app.services.subscription import create_subscription


async def finalize_payment(
    session: AsyncSession, payment: Payment
) -> tuple[str, Subscription | None, User | None]:
    """Обработать успешный платёж (только БД, без отправки сообщений).

    Возвращает (status, subscription, user).
    """
    if payment.status == "succeeded":
        return "ignored", None, None

    user = await session.get(User, payment.user_id)
    if user is None:
        return "ignored", None, None

    snapshot = payment.raw_payload or {}
    balance_used = int(snapshot.get("balance_used", 0) or 0)
    plan_id = snapshot.get("plan_id") or payment.plan_id
    duration_days = int(snapshot.get("duration_days", 30) or 30)
    traffic_gb = int(snapshot.get("traffic_gb", 100) or 100)
    devices_limit = int(snapshot.get("devices_limit", 1) or 1)
    is_trial = bool(snapshot.get("is_trial", False))
    promo_code = snapshot.get("promo_code")

    plan = await session.get(Plan, plan_id) if plan_id else None

    if promo_code:
        promo = await validate_promo(session, promo_code)
        if promo:
            await mark_promo_used(session, promo)

    if balance_used > 0:
        await spend_balance(session, user, balance_used, "Оплата подписки")
    total_paid = balance_used + int(payment.amount or 0)

    client = get_remnawave()
    sub = await create_subscription(
        session,
        client,
        user,
        plan=plan,
        duration_days=duration_days,
        traffic_gb=traffic_gb,
        devices_limit=devices_limit,
        is_trial=is_trial,
        payment_id=payment.id,
        paid_amount=total_paid,
    )

    payment.status = "succeeded"
    payment.subscription_id = sub.id
    payment.paid_at = datetime.now(timezone.utc)

    # Рефералка: процент с первой платной покупки.
    if not is_trial and user.referred_by:
        prior = (
            await session.execute(
                select(func.count(Subscription.id)).where(
                    Subscription.user_id == user.id,
                    Subscription.is_trial.is_(False),
                    Subscription.id != sub.id,
                )
            )
        ).scalar_one()
        if prior == 0:
            referrer = (
                await session.execute(
                    select(User).where(User.telegram_id == user.referred_by)
                )
            ).scalar_one_or_none()
            if referrer:
                bonus = round(total_paid * settings.referral_percent / 100)
                await add_balance(
                    session,
                    referrer,
                    bonus,
                    "referral",
                    f"Реферал tg{user.telegram_id}",
                )

    return "succeeded", sub, user
