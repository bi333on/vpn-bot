"""Общие хелперы обработчиков."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


async def get_or_create_user(
    session: AsyncSession, telegram_id: int, username: str | None
) -> User:
    user = (
        await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
    ).scalar_one_or_none()
    if user is None:
        user = User(telegram_id=telegram_id, username=username)
        session.add(user)
        await session.flush()
    elif username and user.username != username:
        user.username = username
    return user
