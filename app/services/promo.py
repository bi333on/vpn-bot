"""Промокоды: валидация и расчёт скидки."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PromoCode


def compute_discount(price: int, promo: PromoCode) -> tuple[int, int]:
    """Вернуть (итоговая_цена, размер_скидки) в минорных единицах."""
    if promo.discount_type == "percent":
        discount = round(price * promo.discount_value / 100)
    else:
        discount = min(int(promo.discount_value), price)
    discount = max(0, min(discount, price))
    return price - discount, discount


async def validate_promo(session: AsyncSession, code: str) -> PromoCode | None:
    normalized = (code or "").strip().upper()
    if not normalized:
        return None
    row = (
        await session.execute(
            select(PromoCode).where(PromoCode.code == normalized)
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    if not row.is_active:
        return None
    if row.max_uses is not None and row.used_count >= row.max_uses:
        return None
    if row.expires_at is not None and row.expires_at < datetime.now(timezone.utc):
        return None
    return row


async def mark_promo_used(session: AsyncSession, promo: PromoCode) -> None:
    promo.used_count += 1
