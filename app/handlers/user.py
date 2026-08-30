"""Обработчики: /start, меню, рефералка, баланс."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from app.config import settings
from app.db.engine import session_scope
from app.handlers.common import get_or_create_user
from app.keyboards.inline import main_menu
from app.services import referral as referral_service
from app.utils import fmt_money

router = Router()

HELLO_TEXT = (
    "Привет! 👋\n\n"
    "Я бот для покупки VPN (VLESS + Reality).\n"
    "Выбирай тариф, оплачивай и получай готовый конфиг для "
    "v2rayNG / Streisand / Nekoray и других клиентов."
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    parts = message.text.split(maxsplit=1)
    args = parts[1].strip() if len(parts) > 1 else ""
    async with session_scope() as session:
        user = await get_or_create_user(
            session, message.from_user.id, message.from_user.username
        )
        if args and not user.referred_by:
            referrer = await referral_service.find_by_referral_code(session, args)
            if referrer and referrer.telegram_id != user.telegram_id:
                user.referred_by = referrer.telegram_id
        await message.answer(HELLO_TEXT, reply_markup=main_menu())


@router.callback_query(F.data == "menu")
async def cb_menu(cb: CallbackQuery) -> None:
    await cb.message.edit_text(HELLO_TEXT, reply_markup=main_menu())
    await cb.answer()


@router.callback_query(F.data == "balance")
async def cb_balance(cb: CallbackQuery) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(
            session, cb.from_user.id, cb.from_user.username
        )
        text = (
            f"💰 Ваш баланс: <b>{fmt_money(user.balance)}</b>\n\n"
            "Баланс можно потратить на оплату подписки или получить "
            f"{settings.referral_percent}% с покупок приглашённых друзей."
        )
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu())
    await cb.answer()


@router.callback_query(F.data == "referral")
async def cb_referral(cb: CallbackQuery) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(
            session, cb.from_user.id, cb.from_user.username
        )
        code = await referral_service.ensure_referral_code(session, user)
        me = await cb.bot.get_me()
        link = f"https://t.me/{me.username}?start={code}"
        text = (
            "👥 <b>Реферальная программа</b>\n\n"
            f"Ваш код: <code>{code}</code>\n"
            f"Ссылка: {link}\n\n"
            f"Вы получаете <b>{settings.referral_percent}%</b> от первой покупки "
            "приглашённого друга на свой баланс."
        )
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu())
    await cb.answer()
