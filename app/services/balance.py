"""Баланс пользователя: зачисление и списание."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BalanceTransaction, User


async def add_balance(
    session: AsyncSession,
    user: User,
    amount: int,
    type_: str = "manual",
    description: str | None = None,
) -> None:
    if amount <= 0:
        return
    user.balance = int(user.balance or 0) + int(amount)
    session.add(
        BalanceTransaction(
            user_id=user.id,
            amount=int(amount),
            type=type_,
            description=description,
        )
    )


async def spend_balance(
    session: AsyncSession,
    user: User,
    amount: int,
    description: str | None = None,
) -> bool:
    if amount <= 0:
        return True
    if int(user.balance or 0) < int(amount):
        return False
    user.balance = int(user.balance) - int(amount)
    session.add(
        BalanceTransaction(
            user_id=user.id,
            amount=-int(amount),
            type="spend",
            description=description,
        )
    )
    return True
