"""Обработчики: /start, меню, рефералка, баланс, язык."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from app.config import settings
from app.db.engine import session_scope
from app.handlers.common import get_or_create_user
from app.i18n import get_lang, tr
from app.keyboards.inline import main_menu
from app.services import referral as referral_service
from app.utils import fmt_money

router = Router()


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
        lang = get_lang(user)
        await message.answer(tr(lang, "hello"), reply_markup=main_menu(lang))


@router.callback_query(F.data == "menu")
async def cb_menu(cb: CallbackQuery) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(
            session, cb.from_user.id, cb.from_user.username
        )
        lang = get_lang(user)
        await cb.message.edit_text(tr(lang, "hello"), reply_markup=main_menu(lang))
    await cb.answer()


@router.message(Command("lang"))
async def cmd_lang(message: Message) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(
            session, message.from_user.id, message.from_user.username
        )
        user.lang = "en" if get_lang(user) != "en" else "ru"
        lang = get_lang(user)
        await message.answer(
            tr(lang, "lang_switched", lang=lang), reply_markup=main_menu(lang)
        )


@router.callback_query(F.data == "lang")
async def cb_lang(cb: CallbackQuery) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(
            session, cb.from_user.id, cb.from_user.username
        )
        user.lang = "en" if get_lang(user) != "en" else "ru"
        lang = get_lang(user)
        await cb.message.edit_text(tr(lang, "hello"), reply_markup=main_menu(lang))
        await cb.answer(tr(lang, "lang_switched", lang=lang))


@router.callback_query(F.data == "balance")
async def cb_balance(cb: CallbackQuery) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(
            session, cb.from_user.id, cb.from_user.username
        )
        lang = get_lang(user)
        text = tr(
            lang,
            "balance_title",
            balance=fmt_money(user.balance),
            percent=settings.referral_percent,
        )
        await cb.message.edit_text(
            text, parse_mode="HTML", reply_markup=main_menu(lang)
        )
    await cb.answer()


@router.callback_query(F.data == "referral")
async def cb_referral(cb: CallbackQuery) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(
            session, cb.from_user.id, cb.from_user.username
        )
        lang = get_lang(user)
        code = await referral_service.ensure_referral_code(session, user)
        me = await cb.bot.get_me()
        link = f"https://t.me/{me.username}?start={code}"
        text = tr(
            lang,
            "referral_title",
            code=code,
            link=link,
            percent=settings.referral_percent,
        )
        await cb.message.edit_text(
            text, parse_mode="HTML", reply_markup=main_menu(lang)
        )
    await cb.answer()
