"""Inline-клавиатуры бота."""
from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import settings
from app.db.models import Plan
from app.utils import fmt_money


def main_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🛒 Купить", callback_data="buy")
    b.button(text="📱 Мои подписки", callback_data="subs")
    b.button(text="🎁 Пробный период", callback_data="trial")
    b.button(text="👥 Реферальная программа", callback_data="referral")
    b.button(text="💰 Баланс", callback_data="balance")
    b.button(text="💬 Поддержка", url=settings.support_link)
    b.adjust(2)
    return b.as_markup()


def back_to_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔙 В меню", callback_data="menu")
    return b.as_markup()


def plans_keyboard(plans: list[Plan]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for plan in plans:
        label = f"{plan.name} — {fmt_money(plan.price)} / {plan.duration_days} дн"
        b.button(text=label, callback_data=f"plan:{plan.id}")
    b.adjust(1)
    b.button(text="🔙 Назад", callback_data="menu")
    return b.as_markup()


def promo_skip_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Пропустить ➡️", callback_data="skip_promo")
    b.button(text="🔙 Назад", callback_data="buy")
    b.adjust(1)
    return b.as_markup()


def payment_keyboard(
    *, balance: int, price: int, provider_names: list[str]
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if balance >= price:
        b.button(
            text=f"💰 Оплатить с баланса ({fmt_money(price)})",
            callback_data="pay_balance",
        )
    if "yookassa" in provider_names:
        b.button(text="💳 Картой / СБП", callback_data="pay:yookassa")
    if "cryptobot" in provider_names:
        b.button(text="🪙 CryptoBot (USDT)", callback_data="pay:cryptobot")
    if "rollypay" in provider_names:
        b.button(text="🧾 RollyPay", callback_data="pay:rollypay")
    b.button(text="🔙 Назад", callback_data="buy")
    b.adjust(1)
    return b.as_markup()


def subscription_actions(sub_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔗 Конфиг", callback_data=f"cfg:{sub_id}")
    b.button(text="📷 QR", callback_data=f"qr:{sub_id}")
    b.button(text="🔁 Продлить", callback_data=f"renew:{sub_id}")
    b.button(text="🗑 Удалить", callback_data=f"del:{sub_id}")
    b.adjust(2)
    b.button(text="🔙 В меню", callback_data="menu")
    return b.as_markup()


def confirm_delete(sub_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Да, удалить", callback_data=f"del_confirm:{sub_id}")
    b.button(text="❌ Отмена", callback_data=f"cfg:{sub_id}")
    b.adjust(2)
    return b.as_markup()


def renew_keyboard(sub_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Продлить ещё раз", callback_data=f"renew_confirm:{sub_id}")
    b.button(text="❌ Отмена", callback_data="subs")
    b.adjust(2)
    return b.as_markup()


def admin_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📊 Статистика", callback_data="admin:stats")
    b.button(text="👥 Пользователи", callback_data="admin:users")
    b.button(text="📦 Тарифы", callback_data="admin:plans")
    b.button(text="🏷 Промокоды", callback_data="admin:promos")
    b.button(text="➕ Пополнить баланс", callback_data="admin:topup")
    b.button(text="📱 Лимит устройств", callback_data="admin:devices")
    b.button(text="📣 Рассылка", callback_data="admin:broadcast")
    b.adjust(2)
    return b.as_markup()
