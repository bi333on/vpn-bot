"""Автопродление по балансу.

Правило: если на балансе хватает на полный период тарифа — продлеваем на
весь период; иначе, если хватает на 1 день (по дневной цене) — продлеваем
на 1 день; иначе — автопродление невозможно.
"""
from __future__ import annotations

from math import ceil

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Plan, Subscription, User
from app.remnawave.client import RemnawaveClient
from app.services.balance import spend_balance
from app.services.subscription import extend_subscription


def daily_price(plan: Plan) -> int:
    """Дневная цена тарифа (в минорных единицах), округление вверх."""
    if plan.duration_days <= 0:
        return plan.price
    return max(1, ceil(plan.price / plan.duration_days))


async def try_auto_renew(
    session: AsyncSession,
    client: RemnawaveClient,
    sub: Subscription,
    user: User,
) -> str:
    """Попытаться автопродлить подписку.

    Возвращает: 'renewed_full' | 'renewed_day' | 'insufficient' | 'no_plan'.
    """
    if sub.plan_id is None:
        return "no_plan"
    plan = await session.get(Plan, sub.plan_id)
    if plan is None or not plan.is_active:
        return "no_plan"

    balance = int(user.balance or 0)

    if balance >= plan.price:
        if await spend_balance(
            session, user, plan.price, f"Автопродление #{sub.id}"
        ):
            await extend_subscription(
                session,
                client,
                sub,
                duration_days=plan.duration_days,
                traffic_gb=plan.traffic_gb,
                devices_limit=plan.devices_limit,
            )
            return "renewed_full"

    day = daily_price(plan)
    if balance >= day:
        if await spend_balance(
            session, user, day, f"Автопродление на 1 день #{sub.id}"
        ):
            await extend_subscription(session, client, sub, duration_days=1)
            return "renewed_day"

    return "insufficient"
