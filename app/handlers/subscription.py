"""Мои подписки: список, конфиг, QR, продление, удаление, trial."""
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
from app.keyboards.inline import (
    confirm_delete,
    main_menu,
    renew_keyboard,
    subscription_actions,
)
from app.services.balance import spend_balance
from app.services.messaging import send_subscription_config
from app.services.qr import make_qr_png
from app.services.subscription import (
    create_subscription,
    delete_subscription,
    extend_subscription,
)
from app.utils import fmt_bytes, fmt_money

router = Router()


def _sub_detail(sub: Subscription) -> str:
    emoji = "🟢" if sub.status == "active" else "🔴"
    date = sub.expires_at.strftime("%d.%m.%Y") if sub.expires_at else "—"
    label = "Trial" if sub.is_trial else "Подписка"
    return (
        f"{emoji} <b>{label} #{sub.id}</b>\n"
        f"Трафик: {fmt_bytes(sub.traffic_used_bytes)} / "
        f"{fmt_bytes(sub.traffic_limit_bytes)}\n"
        f"До: {date} · Устройств: {sub.devices_limit}"
    )


@router.callback_query(F.data == "subs")
async def cb_subs(cb: CallbackQuery) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(
            session, cb.from_user.id, cb.from_user.username
        )
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
            await cb.message.edit_text(
                "У вас пока нет подписок. Купите первую! 🛒",
                reply_markup=main_menu(),
            )
            await cb.answer()
            return
        kb = InlineKeyboardBuilder()
        for sub in subs:
            kb.button(text=f"Открыть #{sub.id}", callback_data=f"sub:{sub.id}")
        kb.adjust(1)
        kb.button(text="🔙 В меню", callback_data="menu")
        text = "Ваши подписки:\n\n" + "\n\n".join(_sub_detail(s) for s in subs)
        await cb.message.edit_text(
            text, parse_mode="HTML", reply_markup=kb.as_markup()
        )
    await cb.answer()


@router.callback_query(F.data.startswith("sub:"))
async def cb_sub(cb: CallbackQuery) -> None:
    sub_id = int(cb.data.split(":")[1])
    async with session_scope() as session:
        sub = await session.get(Subscription, sub_id)
        if sub is None:
            await cb.answer("Подписка не найдена", show_alert=True)
            return
        await cb.message.edit_text(
            _sub_detail(sub),
            parse_mode="HTML",
            reply_markup=subscription_actions(sub.id),
        )
    await cb.answer()


@router.callback_query(F.data.startswith("cfg:"))
async def cb_cfg(cb: CallbackQuery) -> None:
    sub_id = int(cb.data.split(":")[1])
    async with session_scope() as session:
        sub = await session.get(Subscription, sub_id)
        if sub is None or not sub.config_link:
            await cb.answer("Конфиг недоступен", show_alert=True)
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
        if sub is None or not sub.config_link:
            await cb.answer("Конфиг недоступен", show_alert=True)
            return
        png = make_qr_png(sub.config_link)
        await cb.message.answer_photo(
            BufferedInputFile(png, filename="vpn_qr.png")
        )
    await cb.answer()


@router.callback_query(F.data.startswith("del:"))
async def cb_del(cb: CallbackQuery) -> None:
    sub_id = int(cb.data.split(":")[1])
    await cb.message.edit_text(
        "Удалить подписку? Конфиг перестанет работать.",
        reply_markup=confirm_delete(sub_id),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("del_confirm:"))
async def cb_del_confirm(cb: CallbackQuery) -> None:
    sub_id = int(cb.data.split(":")[1])
    async with session_scope() as session:
        sub = await session.get(Subscription, sub_id)
        if sub is None:
            await cb.answer("Подписка не найдена", show_alert=True)
            return
        try:
            await delete_subscription(session, get_remnawave(), sub)
        except Exception as exc:  # noqa: BLE001
            await cb.answer(f"Ошибка удаления: {exc}", show_alert=True)
            return
        await cb.message.edit_text("Подписка удалена.", reply_markup=main_menu())
    await cb.answer()


@router.callback_query(F.data.startswith("renew:"))
async def cb_renew(cb: CallbackQuery) -> None:
    sub_id = int(cb.data.split(":")[1])
    async with session_scope() as session:
        sub = await session.get(Subscription, sub_id)
        if sub is None or sub.plan_id is None:
            await cb.answer("Подписку нельзя продлить", show_alert=True)
            return
        plan = await session.get(Plan, sub.plan_id)
        await cb.message.edit_text(
            f"Продлить на {plan.duration_days} дн за {fmt_money(plan.price)} "
            "(оплата с баланса)?",
            reply_markup=renew_keyboard(sub.id),
        )
    await cb.answer()


@router.callback_query(F.data.startswith("renew_confirm:"))
async def cb_renew_confirm(cb: CallbackQuery) -> None:
    sub_id = int(cb.data.split(":")[1])
    async with session_scope() as session:
        user = await get_or_create_user(
            session, cb.from_user.id, cb.from_user.username
        )
        sub = await session.get(Subscription, sub_id)
        plan = await session.get(Plan, sub.plan_id)
        if sub is None or plan is None:
            await cb.answer("Подписка не найдена", show_alert=True)
            return
        ok = await spend_balance(
            session, user, plan.price, f"Продление подписки #{sub.id}"
        )
        if not ok:
            await cb.answer(
                "Недостаточно средств. Купите новый тариф или пополните баланс.",
                show_alert=True,
            )
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
            await cb.answer(f"Ошибка продления: {exc}", show_alert=True)
            return
        await cb.message.answer("✅ Подписка продлена.")
    await cb.answer()


@router.callback_query(F.data == "trial")
async def cb_trial(cb: CallbackQuery) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(
            session, cb.from_user.id, cb.from_user.username
        )
        if not settings.trial_enabled or user.trial_used:
            await cb.message.edit_text(
                "Пробный период недоступен.", reply_markup=main_menu()
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
            await cb.answer(f"Ошибка активации: {exc}", show_alert=True)
            return
        user.trial_used = True
        await cb.message.answer("🎁 Пробный период активирован!")
        await send_subscription_config(cb.bot, user, sub)
    await cb.answer()
