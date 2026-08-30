"""Реферальная система."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.utils import generate_referral_code


async def ensure_referral_code(session: AsyncSession, user: User) -> str:
    if user.referral_code:
        return user.referral_code
    for _ in range(5):
        code = generate_referral_code()
        exists = (
            await session.execute(
                select(User.id).where(User.referral_code == code)
            )
        ).first()
        if not exists:
            user.referral_code = code
            return code
    raise RuntimeError("cannot generate unique referral code")


async def find_by_referral_code(
    session: AsyncSession, code: str
) -> User | None:
    normalized = (code or "").strip().upper()
    if not normalized:
        return None
    return (
        await session.execute(
            select(User).where(User.referral_code == normalized)
        )
    ).scalar_one_or_none()
