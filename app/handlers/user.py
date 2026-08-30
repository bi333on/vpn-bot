"""Обработчики: личный кабинет, рефералка, баланс, язык."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select

from app.config import settings
from app.db.engine import session_scope
from app.db.models import Subscription
from app.handlers.common import get_or_create_user
from app.i18n import get_lang, tr
from app.keyboards.inline import back_to_menu, cabinet_keyboard
from app.services import referral as referral_service
from app.utils import fmt_money

router = Router()


async def _render_cabinet(session, user) -> tuple[str, str]:
    lang = get_lang(user)
    active = (
        await session.execute(
            select(func.count(Subscription.id)).where(
                Subscription.user_id == user.id,
                Subscription.status == "active",
            )
        )
    ).scalar_one()
    name = user.first_name or user.username or f"tg{user.telegram_id}"
    text = "\n".join(
        [
            f"<b>{tr(lang, 'cabinet_title')}</b>",
            tr(lang, "cabinet_profile", name=name),
            "",
            tr(lang, "cabinet_id", tg_id=user.telegram_id),
            tr(lang, "cabinet_balance", balance=fmt_money(user.balance)),
            tr(lang, "cabinet_subs_count", count=active),
        ]
    )
    return text, lang


def _cabinet_kb(lang: str, user_id: int):
    return cabinet_keyboard(
        lang,
        is_admin=user_id in settings.admin_ids,
        channel_link=settings.channel_link,
        web_link=settings.web_link,
    )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    parts = message.text.split(maxsplit=1)
    args = parts[1].strip() if len(parts) > 1 else ""
    async with session_scope() as session:
        user = await get_or_create_user(
            session,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
        )
        if args and not user.referred_by:
            referrer = await referral_service.find_by_referral_code(session, args)
            if referrer and referrer.telegram_id != user.telegram_id:
                user.referred_by = referrer.telegram_id
        text, lang = await _render_cabinet(session, user)
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=_cabinet_kb(lang, message.from_user.id),
        )


@router.callback_query(F.data == "menu")
async def cb_menu(cb: CallbackQuery) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(
            session,
            cb.from_user.id,
            cb.from_user.username,
            cb.from_user.first_name,
        )
        text, lang = await _render_cabinet(session, user)
        await cb.message.edit_text(
            text, parse_mode="HTML", reply_markup=_cabinet_kb(lang, cb.from_user.id)
        )
    await cb.answer()


@router.message(Command("lang"))
async def cmd_lang(message: Message) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(
            session,
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
        )
        user.lang = "en" if get_lang(user) != "en" else "ru"
        lang = get_lang(user)
        await message.answer(
            tr(lang, "lang_switched", lang=lang), reply_markup=back_to_menu(lang)
        )


@router.callback_query(F.data == "lang")
async def cb_lang(cb: CallbackQuery) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(
            session,
            cb.from_user.id,
            cb.from_user.username,
            cb.from_user.first_name,
        )
        user.lang = "en" if get_lang(user) != "en" else "ru"
        lang = get_lang(user)
        text, _ = await _render_cabinet(session, user)
        await cb.message.edit_text(
            text, parse_mode="HTML", reply_markup=_cabinet_kb(lang, cb.from_user.id)
        )
        await cb.answer(tr(lang, "lang_switched", lang=lang))


@router.callback_query(F.data == "balance")
async def cb_balance(cb: CallbackQuery) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(
            session,
            cb.from_user.id,
            cb.from_user.username,
            cb.from_user.first_name,
        )
        lang = get_lang(user)
        text = tr(
            lang,
            "balance_title",
            balance=fmt_money(user.balance),
            percent=settings.referral_percent,
        )
        await cb.message.edit_text(
            text, parse_mode="HTML", reply_markup=back_to_menu(lang)
        )
    await cb.answer()


@router.callback_query(F.data == "referral")
async def cb_referral(cb: CallbackQuery) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(
            session,
            cb.from_user.id,
            cb.from_user.username,
            cb.from_user.first_name,
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
            text, parse_mode="HTML", reply_markup=back_to_menu(lang)
        )
    await cb.answer()


@router.callback_query(F.data == "about")
async def cb_about(cb: CallbackQuery) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(
            session,
            cb.from_user.id,
            cb.from_user.username,
            cb.from_user.first_name,
        )
        lang = get_lang(user)
        await cb.message.edit_text(
            tr(lang, "about_text"),
            parse_mode="HTML",
            reply_markup=back_to_menu(lang),
        )
    await cb.answer()


@router.callback_query(F.data == "gift")
async def cb_gift(cb: CallbackQuery) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(
            session,
            cb.from_user.id,
            cb.from_user.username,
            cb.from_user.first_name,
        )
        lang = get_lang(user)
        await cb.message.edit_text(
            tr(lang, "gift_wip"),
            parse_mode="HTML",
            reply_markup=back_to_menu(lang),
        )
    await cb.answer()
