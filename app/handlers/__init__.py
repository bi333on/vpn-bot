"""Регистрация обработчиков в диспетчере."""
from __future__ import annotations

from aiogram import Dispatcher

from app.handlers import admin, purchase, subscription, user


def register_handlers(dp: Dispatcher) -> None:
    dp.include_router(user.router)
    dp.include_router(purchase.router)
    dp.include_router(subscription.router)
    dp.include_router(admin.router)
