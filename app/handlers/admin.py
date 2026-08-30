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
from app.keyboards.inline import admin_menu, cancel_keyboard
from app.services.balance import add_balance
from app.services.design import (
    BUTTON_SLOTS,
    SCREENS,
    get_design,
    save_design,
    slot_emoji,
)
from app.services.git_update import (
    check_updates,
    current_commit,
    git_pull,
    mark_update_pending,
    restart,
)
from app.services.remnawave_config import (
    get_remnawave_api_token,
    get_remnawave_api_url,
    get_remnawave_node_uuid,
    set_remnawave_api_token,
    set_remnawave_api_url,
    set_remnawave_node_uuid,
)
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

    remnawave_url = State()
    remnawave_token = State()
    remnawave_node = State()

    broadcast_text = State()

    design_emoji = State()
    design_label = State()
    design_btn_label = State()
    design_btn_url = State()
    design_img = State()


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    await message.answer("🛠 Админ-панель", reply_markup=admin_menu())


@router.message(Command("cancel"), StateFilter("*"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=admin_menu())


@router.callback_query(F.data == "admin:cancel", StateFilter("*"))
async def cb_admin_cancel(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.message.edit_text("Действие отменено.", reply_markup=admin_menu())
    await cb.answer()


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
    await cb.message.edit_text(
        "Введите название тарифа:", reply_markup=cancel_keyboard()
    )
    await cb.answer()


@router.message(AdminFlow.add_plan_name)
async def add_plan_name(message: Message, state: FSMContext) -> None:
    await state.update_data(plan_name=message.text.strip())
    await state.set_state(AdminFlow.add_plan_price)
    await message.answer(
        "Цена в рублях (например 149):", reply_markup=cancel_keyboard()
    )


@router.message(AdminFlow.add_plan_price)
async def add_plan_price(message: Message, state: FSMContext) -> None:
    try:
        rubles = int(message.text.strip())
    except ValueError:
        await message.answer(
            "Введите целое число рублей.", reply_markup=cancel_keyboard()
        )
        return
    await state.update_data(plan_price=rubles * 100)
    await state.set_state(AdminFlow.add_plan_days)
    await message.answer("Срок действия (дней):", reply_markup=cancel_keyboard())


@router.message(AdminFlow.add_plan_days)
async def add_plan_days(message: Message, state: FSMContext) -> None:
    try:
        days = int(message.text.strip())
    except ValueError:
        await message.answer(
            "Введите целое число дней.", reply_markup=cancel_keyboard()
        )
        return
    await state.update_data(plan_days=days)
    await state.set_state(AdminFlow.add_plan_gb)
    await message.answer("Трафик (ГБ):", reply_markup=cancel_keyboard())


@router.message(AdminFlow.add_plan_gb)
async def add_plan_gb(message: Message, state: FSMContext) -> None:
    try:
        gb = int(message.text.strip())
    except ValueError:
        await message.answer(
            "Введите целое число ГБ.", reply_markup=cancel_keyboard()
        )
        return
    await state.update_data(plan_gb=gb)
    await state.set_state(AdminFlow.add_plan_devices)
    await message.answer(
        "Лимит устройств (hwidDeviceLimit):", reply_markup=cancel_keyboard()
    )


@router.message(AdminFlow.add_plan_devices)
async def add_plan_devices(message: Message, state: FSMContext) -> None:
    try:
        devices = int(message.text.strip())
    except ValueError:
        await message.answer(
            "Введите целое число.", reply_markup=cancel_keyboard()
        )
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
    await cb.message.edit_text(
        "Код промокода (например SUMMER25):", reply_markup=cancel_keyboard()
    )
    await cb.answer()


@router.message(AdminFlow.add_promo_code)
async def add_promo_code(message: Message, state: FSMContext) -> None:
    code = (message.text or "").strip().upper()
    await state.update_data(promo_code=code)
    await state.set_state(AdminFlow.add_promo_type)
    await message.answer(
        "Тип скидки: введите `percent` или `fixed`:", reply_markup=cancel_keyboard()
    )


@router.message(AdminFlow.add_promo_type)
async def add_promo_type(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip().lower()
    if value not in ("percent", "fixed"):
        await message.answer(
            "Введите `percent` или `fixed`.", reply_markup=cancel_keyboard()
        )
        return
    await state.update_data(promo_type=value)
    await state.set_state(AdminFlow.add_promo_value)
    await message.answer(
        "Значение: для percent — процент (1-100), для fixed — сумма в рублях:",
        reply_markup=cancel_keyboard(),
    )


@router.message(AdminFlow.add_promo_value)
async def add_promo_value(message: Message, state: FSMContext) -> None:
    try:
        value = int(message.text.strip())
    except ValueError:
        await message.answer(
            "Введите целое число.", reply_markup=cancel_keyboard()
        )
        return
    data = await state.get_data()
    if data["promo_type"] == "fixed":
        value = value * 100  # в копейки
    await state.update_data(promo_value=value)
    await state.set_state(AdminFlow.add_promo_max_uses)
    await message.answer(
        "Максимум использований (0 = без ограничения):", reply_markup=cancel_keyboard()
    )


@router.message(AdminFlow.add_promo_max_uses)
async def add_promo_max_uses(message: Message, state: FSMContext) -> None:
    try:
        max_uses = int(message.text.strip())
    except ValueError:
        await message.answer(
            "Введите целое число.", reply_markup=cancel_keyboard()
        )
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
    await cb.message.edit_text(
        "Введите Telegram ID пользователя:", reply_markup=cancel_keyboard()
    )
    await cb.answer()


@router.message(AdminFlow.topup_user)
async def topup_user(message: Message, state: FSMContext) -> None:
    try:
        tg_id = int(message.text.strip())
    except ValueError:
        await message.answer(
            "Введите числовой Telegram ID.", reply_markup=cancel_keyboard()
        )
        return
    await state.update_data(topup_tg=tg_id)
    await state.set_state(AdminFlow.topup_amount)
    await message.answer("Сумма пополнения в рублях:", reply_markup=cancel_keyboard())


@router.message(AdminFlow.topup_amount)
async def topup_amount(message: Message, state: FSMContext) -> None:
    try:
        rubles = int(message.text.strip())
    except ValueError:
        await message.answer(
            "Введите целое число рублей.", reply_markup=cancel_keyboard()
        )
        return
    data = await state.get_data()
    async with session_scope() as session:
        user = (
            await session.execute(
                select(User).where(User.telegram_id == data["topup_tg"])
            )
        ).scalar_one_or_none()
        if user is None:
            await message.answer(
                "Пользователь не найден.", reply_markup=admin_menu()
            )
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
    await cb.message.edit_text(
        "Введите Telegram ID пользователя:", reply_markup=cancel_keyboard()
    )
    await cb.answer()


@router.message(AdminFlow.devices_user)
async def devices_user(message: Message, state: FSMContext) -> None:
    try:
        tg_id = int(message.text.strip())
    except ValueError:
        await message.answer(
            "Введите числовой Telegram ID.", reply_markup=cancel_keyboard()
        )
        return
    async with session_scope() as session:
        user = (
            await session.execute(
                select(User).where(User.telegram_id == tg_id)
            )
        ).scalar_one_or_none()
        if user is None:
            await message.answer(
                "Пользователь не найден.", reply_markup=admin_menu()
            )
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
            await message.answer(
                "У пользователя нет активных подписок.", reply_markup=admin_menu()
            )
            await state.clear()
            return
        sub = subs[0]
        await state.update_data(devices_sub_id=sub.id)
        await state.set_state(AdminFlow.devices_limit)
        await message.answer(
            f"Активная подписка #{sub.id}, текущий лимит: {sub.devices_limit}.\n"
            "Введите новый лимит устройств:",
            reply_markup=cancel_keyboard(),
        )


@router.message(AdminFlow.devices_limit)
async def devices_limit(message: Message, state: FSMContext) -> None:
    try:
        limit = int(message.text.strip())
    except ValueError:
        await message.answer(
            "Введите целое число.", reply_markup=cancel_keyboard()
        )
        return
    if limit < 1:
        await message.answer(
            "Лимит должен быть >= 1.", reply_markup=cancel_keyboard()
        )
        return
    data = await state.get_data()
    async with session_scope() as session:
        sub = await session.get(Subscription, data["devices_sub_id"])
        try:
            await set_device_limit(session, get_remnawave(), sub, limit)
        except Exception as exc:  # noqa: BLE001
            await message.answer(f"Ошибка: {exc}", reply_markup=admin_menu())
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
    await cb.message.edit_text(
        "Введите текст рассылки:", reply_markup=cancel_keyboard()
    )
    await cb.answer()


@router.message(AdminFlow.broadcast_text)
async def broadcast_text(message: Message, state: FSMContext) -> None:
    # html_text сохраняет сущности, включая кастомные эмодзи (<tg-emoji>).
    text = message.html_text or message.text or ""
    async with session_scope() as session:
        users = (await session.execute(select(User))).scalars().all()
    sent = 0
    for u in users:
        try:
            await message.bot.send_message(
                u.telegram_id, text, parse_mode="HTML"
            )
            sent += 1
        except Exception:  # noqa: BLE001
            continue
    await state.clear()
    await message.answer(
        f"✅ Рассылка завершена: доставлено {sent} из {len(users)}.",
        reply_markup=admin_menu(),
    )


# ---------- Remnawave адрес (URL) ----------
@router.callback_query(F.data == "admin:rwurl")
async def cb_rwurl(cb: CallbackQuery, state: FSMContext) -> None:
    async with session_scope() as session:
        url = await get_remnawave_api_url(session)
    await state.set_state(AdminFlow.remnawave_url)
    await cb.message.edit_text(
        f"🔗 Текущий адрес Remnawave: {url or '—'}\n\n"
        "Отправьте URL панели (https://panel.example.com):",
        reply_markup=cancel_keyboard(),
    )
    await cb.answer()


@router.message(AdminFlow.remnawave_url)
async def on_remnawave_url(message: Message, state: FSMContext) -> None:
    url = (message.text or "").strip()
    if not url:
        await message.answer(
            "Введите URL панели.", reply_markup=cancel_keyboard()
        )
        return
    async with session_scope() as session:
        await set_remnawave_api_url(session, url)
    get_remnawave().set_api_url(url)
    await state.clear()
    await message.answer(
        "✅ Адрес Remnawave сохранён.", reply_markup=admin_menu()
    )


# ---------- Remnawave API-токен ----------
@router.callback_query(F.data == "admin:rwkey")
async def cb_rwkey(cb: CallbackQuery, state: FSMContext) -> None:
    async with session_scope() as session:
        token = await get_remnawave_api_token(session)
    masked = (token[:6] + "…") if token else "—"
    await state.set_state(AdminFlow.remnawave_token)
    await cb.message.edit_text(
        f"🔑 Текущий API-токен Remnawave: {masked}\n\n"
        "Отправьте новый токен:",
        reply_markup=cancel_keyboard(),
    )
    await cb.answer()


@router.message(AdminFlow.remnawave_token)
async def on_remnawave_token(message: Message, state: FSMContext) -> None:
    token = (message.text or "").strip()
    if not token:
        await message.answer("Введите токен.", reply_markup=cancel_keyboard())
        return
    async with session_scope() as session:
        await set_remnawave_api_token(session, token)
    get_remnawave().set_api_token(token)
    await state.clear()
    await message.answer(
        "✅ API-токен Remnawave сохранён.", reply_markup=admin_menu()
    )


# ---------- Remnawave нода (UUID) ----------
@router.callback_query(F.data == "admin:rwnode")
async def cb_rwnode(cb: CallbackQuery, state: FSMContext) -> None:
    async with session_scope() as session:
        node_uuid = await get_remnawave_node_uuid(session)
    await state.set_state(AdminFlow.remnawave_node)
    await cb.message.edit_text(
        f"🖧 Текущая нода Remnawave: {node_uuid or '—'}\n\n"
        "Отправьте UUID ноды (XRay-node), на которой выдавать пользователей "
        "(пустая строка — все ноды):",
        reply_markup=cancel_keyboard(),
    )
    await cb.answer()


@router.message(AdminFlow.remnawave_node)
async def on_remnawave_node(message: Message, state: FSMContext) -> None:
    node_uuid = (message.text or "").strip()
    async with session_scope() as session:
        await set_remnawave_node_uuid(session, node_uuid)
    get_remnawave().set_node_uuid(node_uuid or None)
    await state.clear()
    await message.answer(
        "✅ Нода Remnawave сохранена.", reply_markup=admin_menu()
    )


# ---------- дизайн ----------
@router.callback_query(F.data == "admin:design")
async def cb_design(cb: CallbackQuery) -> None:
    kb = InlineKeyboardBuilder()
    kb.button(text="😊 Эмодзи кнопок", callback_data="admin:design:emoji")
    kb.button(text="🏷 Тексты кнопок", callback_data="admin:design:labels")
    kb.button(text="🔘 Конструктор кнопок", callback_data="admin:design:buttons")
    kb.button(text="🖼 Картинки", callback_data="admin:design:images")
    kb.button(text="📋 Шпаргалка Callback", callback_data="admin:design:help")
    kb.button(text="🔙 Назад", callback_data="admin:back")
    kb.adjust(1)
    await cb.message.edit_text(
        "🎨 <b>Дизайн</b>", parse_mode="HTML", reply_markup=kb.as_markup()
    )
    await cb.answer()


@router.callback_query(F.data == "admin:design:help")
async def cb_design_help(cb: CallbackQuery) -> None:
    lines = ["📋 <b>Шпаргалка по кнопкам кабинета</b>", ""]
    for slot, emoji, _label, callback in BUTTON_SLOTS:
        lines.append(f"{emoji} — <code>{callback}</code>")
    lines.append("")
    lines.append("Кастомные кнопки из конструктора — это URL-ссылки.")
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Назад", callback_data="admin:design")
    await cb.message.edit_text(
        "\n".join(lines), parse_mode="HTML", reply_markup=kb.as_markup()
    )
    await cb.answer()


@router.callback_query(F.data == "admin:design:emoji")
async def cb_design_emoji(cb: CallbackQuery) -> None:
    async with session_scope() as session:
        design = await get_design(session)
    kb = InlineKeyboardBuilder()
    for slot, _e, _l, _c in BUTTON_SLOTS:
        cur = slot_emoji(slot, design)
        kb.button(text=f"{slot}: {cur}", callback_data=f"admin:design:emoji:{slot}")
    kb.button(text="🔙 Назад", callback_data="admin:design")
    kb.adjust(1)
    await cb.message.edit_text(
        "😊 Выберите кнопку для замены эмодзи:", reply_markup=kb.as_markup()
    )
    await cb.answer()


@router.callback_query(F.data.startswith("admin:design:emoji:"))
async def cb_design_emoji_slot(cb: CallbackQuery, state: FSMContext) -> None:
    slot = cb.data.rsplit(":", 1)[1]
    await state.update_data(design_slot=slot)
    await state.set_state(AdminFlow.design_emoji)
    await cb.message.edit_text(
        f"Отправьте эмодзи для кнопки <b>{slot}</b> (обычный эмодзи или custom-emoji ID):",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    await cb.answer()


@router.message(AdminFlow.design_emoji)
async def on_design_emoji(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if not value:
        await message.answer("Введите эмодзи или ID.", reply_markup=cancel_keyboard())
        return
    data = await state.get_data()
    slot = data["design_slot"]
    async with session_scope() as session:
        design = await get_design(session)
        design.setdefault("emoji", {})[slot] = value
        await save_design(session, design)
    await state.clear()
    await message.answer(f"✅ Эмодзи для {slot} сохранён.", reply_markup=admin_menu())


@router.callback_query(F.data == "admin:design:labels")
async def cb_design_labels(cb: CallbackQuery) -> None:
    async with session_scope() as session:
        design = await get_design(session)
    kb = InlineKeyboardBuilder()
    for slot, _e, label_key, _c in BUTTON_SLOTS:
        cur = (design.get("labels") or {}).get(slot) or label_key
        kb.button(text=f"{slot}: {cur}", callback_data=f"admin:design:label:{slot}")
    kb.button(text="🔙 Назад", callback_data="admin:design")
    kb.adjust(1)
    await cb.message.edit_text(
        "🏷 Выберите кнопку для изменения текста:", reply_markup=kb.as_markup()
    )
    await cb.answer()


@router.callback_query(F.data.startswith("admin:design:label:"))
async def cb_design_label_slot(cb: CallbackQuery, state: FSMContext) -> None:
    slot = cb.data.rsplit(":", 1)[1]
    await state.update_data(design_slot=slot)
    await state.set_state(AdminFlow.design_label)
    await cb.message.edit_text(
        f"Отправьте новый текст для кнопки <b>{slot}</b> (без эмодзи):",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    await cb.answer()


@router.message(AdminFlow.design_label)
async def on_design_label(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if not value:
        await message.answer("Введите текст.", reply_markup=cancel_keyboard())
        return
    data = await state.get_data()
    slot = data["design_slot"]
    async with session_scope() as session:
        design = await get_design(session)
        design.setdefault("labels", {})[slot] = value
        await save_design(session, design)
    await state.clear()
    await message.answer(f"✅ Текст для {slot} сохранён.", reply_markup=admin_menu())


@router.callback_query(F.data == "admin:design:buttons")
async def cb_design_buttons(cb: CallbackQuery) -> None:
    async with session_scope() as session:
        design = await get_design(session)
    kb = InlineKeyboardBuilder()
    for i, btn in enumerate(design.get("buttons") or []):
        kb.button(
            text=f"🗑 {btn.get('label', '')}",
            callback_data=f"admin:design:btn_del:{i}",
        )
    kb.button(text="➕ Добавить кнопку", callback_data="admin:design:btn_add")
    kb.button(text="🔙 Назад", callback_data="admin:design")
    kb.adjust(1)
    await cb.message.edit_text(
        "🔘 Кастомные кнопки (URL-ссылки):", reply_markup=kb.as_markup()
    )
    await cb.answer()


@router.callback_query(F.data == "admin:design:btn_add")
async def cb_design_btn_add(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFlow.design_btn_label)
    await cb.message.edit_text("Текст кнопки:", reply_markup=cancel_keyboard())
    await cb.answer()


@router.message(AdminFlow.design_btn_label)
async def on_design_btn_label(message: Message, state: FSMContext) -> None:
    label = (message.text or "").strip()
    if not label:
        await message.answer("Введите текст кнопки.", reply_markup=cancel_keyboard())
        return
    await state.update_data(design_btn_label=label)
    await state.set_state(AdminFlow.design_btn_url)
    await message.answer("Ссылка (URL):", reply_markup=cancel_keyboard())


@router.message(AdminFlow.design_btn_url)
async def on_design_btn_url(message: Message, state: FSMContext) -> None:
    url = (message.text or "").strip()
    if not url.startswith(("http://", "https://", "t.me/")):
        await message.answer(
            "Введите корректный URL (https://... или t.me/...).",
            reply_markup=cancel_keyboard(),
        )
        return
    data = await state.get_data()
    async with session_scope() as session:
        design = await get_design(session)
        design.setdefault("buttons", []).append(
            {"label": data["design_btn_label"], "url": url}
        )
        await save_design(session, design)
    await state.clear()
    await message.answer("✅ Кнопка добавлена.", reply_markup=admin_menu())


@router.callback_query(F.data.startswith("admin:design:btn_del:"))
async def cb_design_btn_del(cb: CallbackQuery) -> None:
    idx = int(cb.data.rsplit(":", 1)[1])
    async with session_scope() as session:
        design = await get_design(session)
        buttons = design.get("buttons") or []
        if 0 <= idx < len(buttons):
            buttons.pop(idx)
            design["buttons"] = buttons
            await save_design(session, design)
    await cb.message.answer("✅ Кнопка удалена.")
    await cb.answer()


@router.callback_query(F.data == "admin:design:images")
async def cb_design_images(cb: CallbackQuery) -> None:
    async with session_scope() as session:
        design = await get_design(session)
    kb = InlineKeyboardBuilder()
    for screen in SCREENS:
        cur = (design.get("images") or {}).get(screen) or "—"
        kb.button(text=f"{screen}: {cur[:25]}", callback_data=f"admin:design:img:{screen}")
    kb.button(text="🔙 Назад", callback_data="admin:design")
    kb.adjust(1)
    await cb.message.edit_text(
        "🖼 Картинки над экранами (URL или file_id фото).\n"
        "Экраны: cabinet (профиль), balance, buy, subs.",
        reply_markup=kb.as_markup(),
    )
    await cb.answer()


@router.callback_query(F.data.startswith("admin:design:img:"))
async def cb_design_img_slot(cb: CallbackQuery, state: FSMContext) -> None:
    screen = cb.data.rsplit(":", 1)[1]
    await state.update_data(design_screen=screen)
    await state.set_state(AdminFlow.design_img)
    await cb.message.edit_text(
        f"Отправьте URL картинки или file_id для экрана <b>{screen}</b> "
        "(или «удалить», чтобы убрать):",
        parse_mode="HTML",
        reply_markup=cancel_keyboard(),
    )
    await cb.answer()


@router.message(AdminFlow.design_img)
async def on_design_img(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    data = await state.get_data()
    screen = data["design_screen"]
    async with session_scope() as session:
        design = await get_design(session)
        images = design.setdefault("images", {})
        if value and value.lower() not in ("off", "удалить", "remove"):
            images[screen] = value
        else:
            images.pop(screen, None)
        await save_design(session, design)
    await state.clear()
    await message.answer(f"✅ Картинка для {screen} сохранена.", reply_markup=admin_menu())


# ---------- вход из кабинета ----------
@router.callback_query(F.data == "admin_panel")
async def cb_admin_panel(cb: CallbackQuery) -> None:
    if not is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.message.edit_text("🛠 Админ-панель", reply_markup=admin_menu())
    await cb.answer()


# ---------- git-обновление ----------
@router.callback_query(F.data == "admin:git")
async def cb_git(cb: CallbackQuery) -> None:
    sha = await current_commit()
    result = await check_updates()
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Обновить", callback_data="admin:git_pull")
    kb.button(text="🔙 Назад", callback_data="admin:back")
    kb.adjust(2)
    if result["ok"]:
        if result["behind"] > 0:
            text = (
                f"Текущая версия: <code>{sha}</code>\n"
                f"Доступно обновлений: <b>{result['behind']}</b> коммит(ов)."
            )
        else:
            text = (
                f"Текущая версия: <code>{sha}</code>\n"
                "✅ Актуальная версия."
            )
    else:
        text = (
            f"Текущая версия: <code>{sha}</code>\n"
            f"⚠️ Не удалось проверить: {result['error']}\n\n"
            "Обновите вручную на сервере:\n"
            "<code>cd /opt/vpn-bot && git pull && docker compose up -d --build</code>"
        )
    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())
    await cb.answer()


@router.callback_query(F.data == "admin:git_pull")
async def cb_git_pull(cb: CallbackQuery) -> None:
    back_kb = InlineKeyboardBuilder()
    back_kb.button(text="🔙 Назад", callback_data="admin:back")

    out = await git_pull()
    low = out.lower()

    if not out.strip():
        await cb.message.edit_text(
            "❌ git недоступен в контейнере.\n\n"
            "Обновите вручную на сервере:\n"
            "<code>cd /opt/vpn-bot && git pull && docker compose up -d --build</code>",
            parse_mode="HTML",
            reply_markup=back_kb.as_markup(),
        )
        await cb.answer()
        return

    if any(word in low for word in ("fatal", "error", "denied", "could not", "not a git")):
        await cb.message.edit_text(
            f"❌ Ошибка обновления:\n<code>{out[:400]}</code>",
            parse_mode="HTML",
            reply_markup=back_kb.as_markup(),
        )
        await cb.answer()
        return

    if "already up to date" in low:
        await cb.message.edit_text(
            "✅ Уже актуальная версия.", reply_markup=back_kb.as_markup()
        )
        await cb.answer()
        return

    mark_update_pending()
    await cb.message.edit_text("✅ Обновлено. Перезапускаю...")
    await cb.answer()
    restart()


# ---------- назад в меню админа ----------
@router.callback_query(F.data == "admin:back")
async def cb_admin_back(cb: CallbackQuery) -> None:
    await cb.message.edit_text("🛠 Админ-панель", reply_markup=admin_menu())
    await cb.answer()
