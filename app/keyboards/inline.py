"""Inline-клавиатуры бота."""
from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import settings
from app.db.models import Plan
from app.i18n import tr
from app.utils import fmt_money


def main_menu(lang: str = "ru") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=tr(lang, "menu_buy"), callback_data="buy")
    b.button(text=tr(lang, "menu_subs"), callback_data="subs")
    b.button(text=tr(lang, "menu_trial"), callback_data="trial")
    b.button(text=tr(lang, "menu_referral"), callback_data="referral")
    b.button(text=tr(lang, "menu_balance"), callback_data="balance")
    b.button(text=tr(lang, "menu_lang"), callback_data="lang")
    b.button(text=tr(lang, "menu_support"), url=settings.support_link)
    b.adjust(2)
    return b.as_markup()


def cabinet_keyboard(
    lang: str = "ru",
    is_admin: bool = False,
    channel_link: str = "",
    web_link: str = "",
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=tr(lang, "cabinet_buy"), callback_data="buy")
    b.button(text=tr(lang, "cabinet_subs"), callback_data="subs")
    b.button(text=tr(lang, "cabinet_trial"), callback_data="trial")
    b.button(text=tr(lang, "cabinet_balance_btn"), callback_data="balance")
    b.button(text=tr(lang, "cabinet_referral"), callback_data="referral")
    b.button(text=tr(lang, "cabinet_gift"), callback_data="gift")
    b.button(text=tr(lang, "cabinet_about"), callback_data="about")
    b.button(text=tr(lang, "cabinet_lang"), callback_data="lang")
    if is_admin:
        b.button(text=tr(lang, "cabinet_admin"), callback_data="admin_panel")
    if channel_link:
        b.button(text=tr(lang, "cabinet_channel"), url=channel_link)
    if web_link:
        b.button(text=tr(lang, "cabinet_web"), url=web_link)
    b.adjust(1)
    return b.as_markup()


def back_to_menu(lang: str = "ru") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=tr(lang, "back_menu"), callback_data="menu")
    return b.as_markup()


def cancel_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="❌ Отмена", callback_data="admin:cancel")
    return b.as_markup()


def plans_keyboard(plans: list[Plan], lang: str = "ru") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for plan in plans:
        period = tr(lang, "plan_days", days=plan.duration_days)
        label = f"{plan.name} — {fmt_money(plan.price)} / {period}"
        b.button(text=label, callback_data=f"plan:{plan.id}")
    b.adjust(1)
    b.button(text=tr(lang, "back"), callback_data="menu")
    return b.as_markup()


def promo_skip_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=tr(lang, "promo_skip"), callback_data="skip_promo")
    b.button(text=tr(lang, "back"), callback_data="buy")
    b.adjust(1)
    return b.as_markup()


def payment_keyboard(
    *, balance: int, price: int, provider_names: list[str], lang: str = "ru"
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if balance >= price:
        b.button(
            text=tr(lang, "pay_balance_btn", price=fmt_money(price)),
            callback_data="pay_balance",
        )
    if "yookassa" in provider_names:
        b.button(text=tr(lang, "pay_yookassa"), callback_data="pay:yookassa")
    if "cryptobot" in provider_names:
        b.button(text=tr(lang, "pay_cryptobot"), callback_data="pay:cryptobot")
    if "rollypay" in provider_names:
        b.button(text=tr(lang, "pay_rollypay"), callback_data="pay:rollypay")
    b.button(text=tr(lang, "back"), callback_data="buy")
    b.adjust(1)
    return b.as_markup()


def subscription_actions(
    sub_id: int, auto_renew: bool, lang: str = "ru"
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=tr(lang, "sub_cfg"), callback_data=f"cfg:{sub_id}")
    b.button(text=tr(lang, "sub_qr"), callback_data=f"qr:{sub_id}")
    b.button(text=tr(lang, "sub_renew"), callback_data=f"renew:{sub_id}")
    b.button(text=tr(lang, "sub_delete"), callback_data=f"del:{sub_id}")
    b.button(
        text=tr(lang, "autorenew_btn_on" if auto_renew else "autorenew_btn_off"),
        callback_data=f"autorenew:{sub_id}",
    )
    b.adjust(2)
    b.button(text=tr(lang, "back_menu"), callback_data="menu")
    return b.as_markup()


def confirm_delete(sub_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=tr(lang, "del_yes"), callback_data=f"del_confirm:{sub_id}")
    b.button(text=tr(lang, "del_cancel"), callback_data=f"cfg:{sub_id}")
    b.adjust(2)
    return b.as_markup()


def renew_keyboard(sub_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=tr(lang, "renew_yes"), callback_data=f"renew_confirm:{sub_id}")
    b.button(text=tr(lang, "del_cancel"), callback_data="subs")
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
    b.button(text="🔗 Remnawave URL", callback_data="admin:rwurl")
    b.button(text="🔑 Remnawave API", callback_data="admin:rwkey")
    b.button(text="🖧 Нода Remnawave", callback_data="admin:rwnode")
    b.button(text="📣 Рассылка", callback_data="admin:broadcast")
    b.button(text="🔄 Git-обновление", callback_data="admin:git")
    b.adjust(2)
    return b.as_markup()
