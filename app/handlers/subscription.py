"""Мои подписки: список, конфиг, QR, продление, удаление, trial, автопродление."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import BufferedInputFile, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from app.config import settings
from app.context import get_remnawave
from app.db.engine import session_scope
from app.db.models import Plan, Subscription
from app.handlers.common import get_or_create_user
from app.i18n import get_lang, tr
from app.keyboards.inline import (
    back_to_menu,
    confirm_delete,
    renew_keyboard,
    subscription_actions,
)
from app.services.balance import spend_balance
from app.services.design import get_design
from app.services.messaging import send_subscription_config
from app.services.qr import make_qr_png
from app.services.subscription import (
    create_subscription,
    delete_subscription,
    extend_subscription,
)
from app.utils import fmt_bytes, fmt_money

router = Router()


def _sub_detail(sub: Subscription, lang: str) -> str:
    emoji = "🟢" if sub.status == "active" else "🔴"
    date = sub.expires_at.strftime("%d.%m.%Y") if sub.expires_at else "—"
    label = tr(lang, "sub_label_trial" if sub.is_trial else "sub_label")
    auto = tr(lang, "sub_autorenew_on" if sub.auto_renew else "sub_autorenew_off")
    return (
        f"{emoji} <b>{label} #{sub.id}</b>\n"
        f"{tr(lang, 'sub_traffic', used=fmt_bytes(sub.traffic_used_bytes), limit=fmt_bytes(sub.traffic_limit_bytes))}\n"
        f"{tr(lang, 'sub_until', date=date, devices=sub.devices_limit)}\n"
        f"{auto}"
    )


@router.callback_query(F.data == "subs")
async def cb_subs(cb: CallbackQuery) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(
            session, cb.from_user.id, cb.from_user.username
        )
        lang = get_lang(user)
        design = await get_design(session)
        image = (design.get("images") or {}).get("subs") or ""
        subs = (
            (
                await session.execute(
                    select(Subscription)
                    .where(Subscription.user_id == user.id)
                    .order_by(Subscription.id.desc())
                )
            )
            .scalars()
            .all()
        )
        if not subs:
            if image:
                await cb.message.answer_photo(image)
            await cb.message.edit_text(
                tr(lang, "subs_empty"), reply_markup=back_to_menu(lang)
            )
            await cb.answer()
            return
        kb = InlineKeyboardBuilder()
        for sub in subs:
            kb.button(
                text=tr(lang, "sub_open", id=sub.id),
                callback_data=f"sub:{sub.id}",
            )
        kb.adjust(1)
        kb.button(text=tr(lang, "back_menu"), callback_data="menu")
        text = tr(lang, "subs_title") + "\n\n" + "\n\n".join(
            _sub_detail(s, lang) for s in subs
        )
        if image:
            await cb.message.answer_photo(image)
            await cb.message.answer(
                text, parse_mode="HTML", reply_markup=kb.as_markup()
            )
        else:
            await cb.message.edit_text(
                text, parse_mode="HTML", reply_markup=kb.as_markup()
            )
    await cb.answer()


@router.callback_query(F.data.startswith("sub:"))
async def cb_sub(cb: CallbackQuery) -> None:
    sub_id = int(cb.data.split(":")[1])
    async with session_scope() as session:
        sub = await session.get(Subscription, sub_id)
        user = await get_or_create_user(
            session, cb.from_user.id, cb.from_user.username
        )
        lang = get_lang(user)
        if sub is None:
            await cb.answer(tr(lang, "sub_not_found"), show_alert=True)
            return
        await cb.message.edit_text(
            _sub_detail(sub, lang),
            parse_mode="HTML",
            reply_markup=subscription_actions(sub.id, sub.auto_renew, lang),
        )
    await cb.answer()


@router.callback_query(F.data.startswith("autorenew:"))
async def cb_autorenew(cb: CallbackQuery) -> None:
    sub_id = int(cb.data.split(":")[1])
    async with session_scope() as session:
        sub = await session.get(Subscription, sub_id)
        user = await get_or_create_user(
            session, cb.from_user.id, cb.from_user.username
        )
        lang = get_lang(user)
        if sub is None or sub.user_id != user.id:
            await cb.answer(tr(lang, "sub_not_found"), show_alert=True)
            return
        sub.auto_renew = not sub.auto_renew
        await cb.message.edit_text(
            _sub_detail(sub, lang),
            parse_mode="HTML",
            reply_markup=subscription_actions(sub.id, sub.auto_renew, lang),
        )
        await cb.answer(
            tr(lang, "autorenew_on" if sub.auto_renew else "autorenew_off")
        )


@router.callback_query(F.data.startswith("cfg:"))
async def cb_cfg(cb: CallbackQuery) -> None:
    sub_id = int(cb.data.split(":")[1])
    async with session_scope() as session:
        sub = await session.get(Subscription, sub_id)
        user = await get_or_create_user(
            session, cb.from_user.id, cb.from_user.username
        )
        lang = get_lang(user)
        if sub is None or not sub.config_link:
            await cb.answer(tr(lang, "cfg_unavailable"), show_alert=True)
            return
        await cb.message.answer(
            f"<code>{sub.config_link}</code>", parse_mode="HTML"
        )
    await cb.answer()


@router.callback_query(F.data.startswith("qr:"))
async def cb_qr(cb: CallbackQuery) -> None:
    sub_id = int(cb.data.split(":")[1])
    async with session_scope() as session:
        sub = await session.get(Subscription, sub_id)
        user = await get_or_create_user(
            session, cb.from_user.id, cb.from_user.username
        )
        lang = get_lang(user)
        if sub is None or not sub.config_link:
            await cb.answer(tr(lang, "cfg_unavailable"), show_alert=True)
            return
        png = make_qr_png(sub.config_link)
        await cb.message.answer_photo(
            BufferedInputFile(png, filename="vpn_qr.png")
        )
    await cb.answer()


@router.callback_query(F.data.startswith("del:"))
async def cb_del(cb: CallbackQuery) -> None:
    sub_id = int(cb.data.split(":")[1])
    async with session_scope() as session:
        user = await get_or_create_user(
            session, cb.from_user.id, cb.from_user.username
        )
        lang = get_lang(user)
    await cb.message.edit_text(
        tr(lang, "del_confirm"), reply_markup=confirm_delete(sub_id, lang)
    )
    await cb.answer()


@router.callback_query(F.data.startswith("del_confirm:"))
async def cb_del_confirm(cb: CallbackQuery) -> None:
    sub_id = int(cb.data.split(":")[1])
    async with session_scope() as session:
        sub = await session.get(Subscription, sub_id)
        user = await get_or_create_user(
            session, cb.from_user.id, cb.from_user.username
        )
        lang = get_lang(user)
        if sub is None:
            await cb.answer(tr(lang, "sub_not_found"), show_alert=True)
            return
        try:
            await delete_subscription(session, get_remnawave(), sub)
        except Exception as exc:  # noqa: BLE001
            await cb.answer(tr(lang, "renew_error", error=exc), show_alert=True)
            return
        await cb.message.edit_text(
            tr(lang, "deleted"), reply_markup=back_to_menu(lang)
        )
    await cb.answer()


@router.callback_query(F.data.startswith("renew:"))
async def cb_renew(cb: CallbackQuery) -> None:
    sub_id = int(cb.data.split(":")[1])
    async with session_scope() as session:
        sub = await session.get(Subscription, sub_id)
        user = await get_or_create_user(
            session, cb.from_user.id, cb.from_user.username
        )
        lang = get_lang(user)
        if sub is None or sub.plan_id is None:
            await cb.answer(tr(lang, "renew_not_available"), show_alert=True)
            return
        plan = await session.get(Plan, sub.plan_id)
        await cb.message.edit_text(
            tr(
                lang,
                "renew_prompt",
                days=plan.duration_days,
                price=fmt_money(plan.price),
            ),
            reply_markup=renew_keyboard(sub.id, lang),
        )
    await cb.answer()


@router.callback_query(F.data.startswith("renew_confirm:"))
async def cb_renew_confirm(cb: CallbackQuery) -> None:
    sub_id = int(cb.data.split(":")[1])
    async with session_scope() as session:
        user = await get_or_create_user(
            session, cb.from_user.id, cb.from_user.username
        )
        lang = get_lang(user)
        sub = await session.get(Subscription, sub_id)
        plan = await session.get(Plan, sub.plan_id)
        if sub is None or plan is None:
            await cb.answer(tr(lang, "sub_not_found"), show_alert=True)
            return
        ok = await spend_balance(
            session, user, plan.price, f"Продление подписки #{sub.id}"
        )
        if not ok:
            await cb.answer(tr(lang, "renew_insufficient"), show_alert=True)
            return
        try:
            await extend_subscription(
                session,
                get_remnawave(),
                sub,
                duration_days=plan.duration_days,
                traffic_gb=plan.traffic_gb,
                devices_limit=plan.devices_limit,
            )
        except Exception as exc:  # noqa: BLE001
            await cb.answer(tr(lang, "renew_error", error=exc), show_alert=True)
            return
        await cb.message.answer(
            tr(lang, "renewed"), reply_markup=back_to_menu(lang)
        )
    await cb.answer()


@router.callback_query(F.data == "trial")
async def cb_trial(cb: CallbackQuery) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(
            session, cb.from_user.id, cb.from_user.username
        )
        lang = get_lang(user)
        if not settings.trial_enabled or user.trial_used:
            await cb.message.edit_text(
                tr(lang, "trial_unavailable"), reply_markup=back_to_menu(lang)
            )
            await cb.answer()
            return
        try:
            sub = await create_subscription(
                session,
                get_remnawave(),
                user,
                plan=None,
                duration_days=settings.trial_days,
                traffic_gb=settings.trial_gb,
                devices_limit=settings.trial_devices,
                is_trial=True,
                remark="VPN Trial",
            )
        except Exception as exc:  # noqa: BLE001
            await cb.answer(
                tr(lang, "pay_activation_error", error=exc), show_alert=True
            )
            return
        user.trial_used = True
        await cb.message.answer(tr(lang, "trial_activated"))
        await send_subscription_config(cb.bot, user, sub)
    await cb.answer()
