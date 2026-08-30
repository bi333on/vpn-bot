"""Админ-панель: статистика, тарифы, промокоды, пополнение, лимит устройств, рассылка."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import func, select

from app.config import settings
from app.context import get_remnawave
from app.db.engine import session_scope
from app.db.models import Payment, Plan, PromoCode, Subscription, User
from app.keyboards.inline import admin_menu
from app.services.balance import add_balance
from app.services.subscription import set_device_limit
from app.utils import fmt_money

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


class AdminFlow(StatesGroup):
    add_plan_name = State()
    add_plan_price = State()
    add_plan_days = State()
    add_plan_gb = State()
    add_plan_devices = State()

    add_promo_code = State()
    add_promo_type = State()
    add_promo_value = State()
    add_promo_max_uses = State()

    topup_user = State()
    topup_amount = State()

    devices_user = State()
    devices_limit = State()

    broadcast_text = State()


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    await message.answer("🛠 Админ-панель", reply_markup=admin_menu())


@router.message(Command("cancel"), StateFilter("*"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=admin_menu())


# ---------- статистика ----------
@router.callback_query(F.data == "admin:stats")
async def cb_stats(cb: CallbackQuery) -> None:
    async with session_scope() as session:
        users = (await session.execute(select(func.count(User.id)))).scalar_one()
        active = (
            await session.execute(
                select(func.count(Subscription.id)).where(
                    Subscription.status == "active"
                )
            )
        ).scalar_one()
        revenue = (
            await session.execute(
                select(func.coalesce(func.sum(Payment.amount), 0)).where(
                    Payment.status == "succeeded"
                )
            )
        ).scalar_one()
        paying = (
            await session.execute(
                select(func.count(func.distinct(Payment.user_id))).where(
                    Payment.status == "succeeded"
                )
            )
        ).scalar_one()
        text = (
            "📊 <b>Статистика</b>\n\n"
            f"Пользователей: <b>{users}</b>\n"
            f"Активных подписок: <b>{active}</b>\n"
            f"Плативших: <b>{paying}</b>\n"
            f"Выручка: <b>{fmt_money(int(revenue))}</b>"
        )
        await cb.message.edit_text(
            text, parse_mode="HTML", reply_markup=admin_menu()
        )
    await cb.answer()


# ---------- пользователи ----------
@router.callback_query(F.data == "admin:users")
async def cb_users(cb: CallbackQuery) -> None:
    async with session_scope() as session:
        users = (
            (
                await session.execute(
                    select(User).order_by(User.id.desc()).limit(20)
                )
            )
            .scalars()
            .all()
        )
        if not users:
            await cb.message.edit_text(
                "Пользователей нет.", reply_markup=admin_menu()
            )
            await cb.answer()
            return
        lines = ["👥 <b>Последние пользователи</b>", ""]
        for u in users:
            lines.append(
                f"tg{u.telegram_id} — {fmt_money(u.balance)}"
                + (f" (@{u.username})" if u.username else "")
            )
        await cb.message.edit_text(
            "\n".join(lines), parse_mode="HTML", reply_markup=admin_menu()
        )
    await cb.answer()


# ---------- тарифы ----------
@router.callback_query(F.data == "admin:plans")
async def cb_plans(cb: CallbackQuery) -> None:
    async with session_scope() as session:
        plans = (
            (await session.execute(select(Plan).order_by(Plan.position)))
            .scalars()
            .all()
        )
        kb = InlineKeyboardBuilder()
        lines = ["📦 <b>Тарифы</b>", ""]
        for p in plans:
            status = "✅" if p.is_active else "⛔"
            lines.append(
                f"{status} #{p.id} {p.name} — {fmt_money(p.price)} / "
                f"{p.duration_days}д / {p.traffic_gb}ГБ / {p.devices_limit}устр"
            )
        kb.button(text="➕ Добавить тариф", callback_data="admin:addplan")
        kb.button(text="🔙 Назад", callback_data="admin:back")
        kb.adjust(1)
        await cb.message.edit_text(
            "\n".join(lines), parse_mode="HTML", reply_markup=kb.as_markup()
        )
    await cb.answer()


@router.callback_query(F.data == "admin:addplan")
async def cb_addplan(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFlow.add_plan_name)
    await cb.message.edit_text("Введите название тарифа:")
    await cb.answer()


@router.message(AdminFlow.add_plan_name)
async def add_plan_name(message: Message, state: FSMContext) -> None:
    await state.update_data(plan_name=message.text.strip())
    await state.set_state(AdminFlow.add_plan_price)
    await message.answer("Цена в рублях (например 149):")


@router.message(AdminFlow.add_plan_price)
async def add_plan_price(message: Message, state: FSMContext) -> None:
    try:
        rubles = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число рублей.")
        return
    await state.update_data(plan_price=rubles * 100)
    await state.set_state(AdminFlow.add_plan_days)
    await message.answer("Срок действия (дней):")


@router.message(AdminFlow.add_plan_days)
async def add_plan_days(message: Message, state: FSMContext) -> None:
    try:
        days = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число дней.")
        return
    await state.update_data(plan_days=days)
    await state.set_state(AdminFlow.add_plan_gb)
    await message.answer("Трафик (ГБ):")


@router.message(AdminFlow.add_plan_gb)
async def add_plan_gb(message: Message, state: FSMContext) -> None:
    try:
        gb = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число ГБ.")
        return
    await state.update_data(plan_gb=gb)
    await state.set_state(AdminFlow.add_plan_devices)
    await message.answer("Лимит устройств (hwidDeviceLimit):")


@router.message(AdminFlow.add_plan_devices)
async def add_plan_devices(message: Message, state: FSMContext) -> None:
    try:
        devices = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число.")
        return
    data = await state.get_data()
    async with session_scope() as session:
        session.add(
            Plan(
                name=data["plan_name"],
                price=data["plan_price"],
                duration_days=data["plan_days"],
                traffic_gb=data["plan_gb"],
                devices_limit=devices,
            )
        )
    await state.clear()
    await message.answer("✅ Тариф добавлен.", reply_markup=admin_menu())


# ---------- промокоды ----------
@router.callback_query(F.data == "admin:promos")
async def cb_promos(cb: CallbackQuery) -> None:
    async with session_scope() as session:
        promos = (
            (
                await session.execute(
                    select(PromoCode).order_by(PromoCode.id.desc())
                )
            )
            .scalars()
            .all()
        )
        kb = InlineKeyboardBuilder()
        lines = ["🏷 <b>Промокоды</b>", ""]
        for p in promos:
            lines.append(
                f"{p.code} — {p.discount_type}={p.discount_value} "
                f"({p.used_count}/{p.max_uses or '∞'})"
            )
        kb.button(text="➕ Добавить промокод", callback_data="admin:addpromo")
        kb.button(text="🔙 Назад", callback_data="admin:back")
        kb.adjust(1)
        await cb.message.edit_text(
            "\n".join(lines), parse_mode="HTML", reply_markup=kb.as_markup()
        )
    await cb.answer()


@router.callback_query(F.data == "admin:addpromo")
async def cb_addpromo(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFlow.add_promo_code)
    await cb.message.edit_text("Код промокода (например SUMMER25):")
    await cb.answer()


@router.message(AdminFlow.add_promo_code)
async def add_promo_code(message: Message, state: FSMContext) -> None:
    code = (message.text or "").strip().upper()
    await state.update_data(promo_code=code)
    await state.set_state(AdminFlow.add_promo_type)
    await message.answer("Тип скидки: введите `percent` или `fixed`:")


@router.message(AdminFlow.add_promo_type)
async def add_promo_type(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip().lower()
    if value not in ("percent", "fixed"):
        await message.answer("Введите `percent` или `fixed`.")
        return
    await state.update_data(promo_type=value)
    await state.set_state(AdminFlow.add_promo_value)
    await message.answer(
        "Значение: для percent — процент (1-100), для fixed — сумма в рублях:"
    )


@router.message(AdminFlow.add_promo_value)
async def add_promo_value(message: Message, state: FSMContext) -> None:
    try:
        value = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число.")
        return
    data = await state.get_data()
    if data["promo_type"] == "fixed":
        value = value * 100  # в копейки
    await state.update_data(promo_value=value)
    await state.set_state(AdminFlow.add_promo_max_uses)
    await message.answer("Максимум использований (0 = без ограничения):")


@router.message(AdminFlow.add_promo_max_uses)
async def add_promo_max_uses(message: Message, state: FSMContext) -> None:
    try:
        max_uses = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число.")
        return
    data = await state.get_data()
    async with session_scope() as session:
        session.add(
            PromoCode(
                code=data["promo_code"],
                discount_type=data["promo_type"],
                discount_value=data["promo_value"],
                max_uses=max_uses if max_uses > 0 else None,
            )
        )
    await state.clear()
    await message.answer("✅ Промокод добавлен.", reply_markup=admin_menu())


# ---------- пополнение баланса ----------
@router.callback_query(F.data == "admin:topup")
async def cb_topup(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFlow.topup_user)
    await cb.message.edit_text("Введите Telegram ID пользователя:")
    await cb.answer()


@router.message(AdminFlow.topup_user)
async def topup_user(message: Message, state: FSMContext) -> None:
    try:
        tg_id = int(message.text.strip())
    except ValueError:
        await message.answer("Введите числовой Telegram ID.")
        return
    await state.update_data(topup_tg=tg_id)
    await state.set_state(AdminFlow.topup_amount)
    await message.answer("Сумма пополнения в рублях:")


@router.message(AdminFlow.topup_amount)
async def topup_amount(message: Message, state: FSMContext) -> None:
    try:
        rubles = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число рублей.")
        return
    data = await state.get_data()
    async with session_scope() as session:
        user = (
            await session.execute(
                select(User).where(User.telegram_id == data["topup_tg"])
            )
        ).scalar_one_or_none()
        if user is None:
            await message.answer("Пользователь не найден.")
            await state.clear()
            return
        await add_balance(
            session, user, rubles * 100, "manual", "Ручное пополнение"
        )
        await message.answer(
            f"✅ Баланс tg{user.telegram_id} пополнен на {rubles} руб.",
            reply_markup=admin_menu(),
        )
    await state.clear()


# ---------- лимит устройств ----------
@router.callback_query(F.data == "admin:devices")
async def cb_devices(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFlow.devices_user)
    await cb.message.edit_text("Введите Telegram ID пользователя:")
    await cb.answer()


@router.message(AdminFlow.devices_user)
async def devices_user(message: Message, state: FSMContext) -> None:
    try:
        tg_id = int(message.text.strip())
    except ValueError:
        await message.answer("Введите числовой Telegram ID.")
        return
    async with session_scope() as session:
        user = (
            await session.execute(
                select(User).where(User.telegram_id == tg_id)
            )
        ).scalar_one_or_none()
        if user is None:
            await message.answer("Пользователь не найден.")
            await state.clear()
            return
        subs = (
            (
                await session.execute(
                    select(Subscription)
                    .where(
                        Subscription.user_id == user.id,
                        Subscription.status == "active",
                    )
                    .order_by(Subscription.id.desc())
                )
            )
            .scalars()
            .all()
        )
        if not subs:
            await message.answer("У пользователя нет активных подписок.")
            await state.clear()
            return
        sub = subs[0]
        await state.update_data(devices_sub_id=sub.id)
        await state.set_state(AdminFlow.devices_limit)
        await message.answer(
            f"Активная подписка #{sub.id}, текущий лимит: {sub.devices_limit}.\n"
            "Введите новый лимит устройств:"
        )


@router.message(AdminFlow.devices_limit)
async def devices_limit(message: Message, state: FSMContext) -> None:
    try:
        limit = int(message.text.strip())
    except ValueError:
        await message.answer("Введите целое число.")
        return
    if limit < 1:
        await message.answer("Лимит должен быть >= 1.")
        return
    data = await state.get_data()
    async with session_scope() as session:
        sub = await session.get(Subscription, data["devices_sub_id"])
        try:
            await set_device_limit(session, get_remnawave(), sub, limit)
        except Exception as exc:  # noqa: BLE001
            await message.answer(f"Ошибка: {exc}")
            await state.clear()
            return
        await message.answer(
            f"✅ Лимит устройств для подписки #{sub.id} изменён на {limit} "
            "(пересчёт применён в Remnawave).",
            reply_markup=admin_menu(),
        )
    await state.clear()


# ---------- рассылка ----------
@router.callback_query(F.data == "admin:broadcast")
async def cb_broadcast(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFlow.broadcast_text)
    await cb.message.edit_text("Введите текст рассылки:")
    await cb.answer()


@router.message(AdminFlow.broadcast_text)
async def broadcast_text(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    async with session_scope() as session:
        users = (await session.execute(select(User))).scalars().all()
    sent = 0
    for u in users:
        try:
            await message.bot.send_message(u.telegram_id, text)
            sent += 1
        except Exception:  # noqa: BLE001
            continue
    await state.clear()
    await message.answer(
        f"✅ Рассылка завершена: доставлено {sent} из {len(users)}.",
        reply_markup=admin_menu(),
    )


# ---------- назад в меню админа ----------
@router.callback_query(F.data == "admin:back")
async def cb_admin_back(cb: CallbackQuery) -> None:
    await cb.message.edit_text("🛠 Админ-панель", reply_markup=admin_menu())
    await cb.answer()
