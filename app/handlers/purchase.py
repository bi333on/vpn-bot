"""Покупка: выбор тарифа, промокод, способ оплаты."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from app.config import settings
from app.context import get_payments, get_remnawave
from app.db.engine import session_scope
from app.db.models import Payment, Plan
from app.handlers.common import get_or_create_user
from app.keyboards.inline import (
    payment_keyboard,
    plans_keyboard,
    promo_skip_keyboard,
)
from app.services import balance as balance_service
from app.services.messaging import send_subscription_config
from app.services.promo import (
    compute_discount,
    mark_promo_used,
    validate_promo,
)
from app.services.subscription import create_subscription
from app.utils import fmt_money

router = Router()


class PurchaseFlow(StatesGroup):
    waiting_for_promo = State()
    choosing_payment = State()


async def _render_payment(
    session, state: FSMContext, telegram_id: int
) -> tuple[str, InlineKeyboardMarkup]:
    data = await state.get_data()
    plan = await session.get(Plan, int(data["plan_id"]))
    promo_code = data.get("promo_code")
    promo = await validate_promo(session, promo_code) if promo_code else None
    price = plan.price
    discount = 0
    if promo:
        price, discount = compute_discount(plan.price, promo)

    user = await get_or_create_user(session, telegram_id, None)
    balance = int(user.balance or 0)
    providers = get_payments().names()

    lines = [
        f"Тариф: <b>{plan.name}</b>",
        f"Срок: {plan.duration_days} дн",
        f"Трафик: {plan.traffic_gb} ГБ",
        f"Устройства: {plan.devices_limit}",
        "",
    ]
    if discount:
        lines.append(f"Скидка: -{fmt_money(discount)}")
    lines.append(f"Итого: <b>{fmt_money(price)}</b>")
    if 0 < balance < price:
        lines.append(
            f"Баланс {fmt_money(balance)} будет применён, "
            f"к доплате {fmt_money(price - balance)}"
        )
    text = "\n".join(lines)
    return text, payment_keyboard(
        balance=balance, price=price, provider_names=providers
    )


@router.callback_query(F.data == "buy")
async def cb_buy(cb: CallbackQuery, state: FSMContext) -> None:
    async with session_scope() as session:
        plans = (
            (
                await session.execute(
                    select(Plan)
                    .where(Plan.is_active.is_(True))
                    .order_by(Plan.position)
                )
            )
            .scalars()
            .all()
        )
        if not plans:
            await cb.message.edit_text(
                "Тарифы пока не настроены. Обратитесь в поддержку."
            )
            await cb.answer()
            return
        await state.clear()
        await cb.message.edit_text(
            "Выберите тариф:", reply_markup=plans_keyboard(plans)
        )
    await cb.answer()


@router.callback_query(F.data.startswith("plan:"))
async def cb_plan(cb: CallbackQuery, state: FSMContext) -> None:
    plan_id = int(cb.data.split(":")[1])
    await state.update_data(plan_id=plan_id, promo_code=None)
    await state.set_state(PurchaseFlow.waiting_for_promo)
    await cb.message.edit_text(
        "Введите промокод (если есть) или нажмите «Пропустить»:",
        reply_markup=promo_skip_keyboard(),
    )
    await cb.answer()


@router.message(PurchaseFlow.waiting_for_promo)
async def on_promo(message: Message, state: FSMContext) -> None:
    code = (message.text or "").strip()
    async with session_scope() as session:
        promo = await validate_promo(session, code)
        if promo is None:
            await message.answer(
                "Промокод не найден или недействителен. Попробуйте ещё раз "
                "или нажмите «Пропустить».",
                reply_markup=promo_skip_keyboard(),
            )
            return
        await state.update_data(promo_code=promo.code)
        await state.set_state(PurchaseFlow.choosing_payment)
        text, kb = await _render_payment(session, state, message.from_user.id)
        await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(
    F.data == "skip_promo", StateFilter(PurchaseFlow.waiting_for_promo)
)
async def cb_skip_promo(cb: CallbackQuery, state: FSMContext) -> None:
    async with session_scope() as session:
        await state.set_state(PurchaseFlow.choosing_payment)
        text, kb = await _render_payment(session, state, cb.from_user.id)
        await cb.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await cb.answer()


@router.callback_query(
    F.data == "pay_balance", StateFilter(PurchaseFlow.choosing_payment)
)
async def cb_pay_balance(cb: CallbackQuery, state: FSMContext) -> None:
    async with session_scope() as session:
        user = await get_or_create_user(
            session, cb.from_user.id, cb.from_user.username
        )
        data = await state.get_data()
        plan = await session.get(Plan, int(data["plan_id"]))
        promo = (
            await validate_promo(session, data.get("promo_code"))
            if data.get("promo_code")
            else None
        )
        price = plan.price
        if promo:
            price, _ = compute_discount(plan.price, promo)

        ok = await balance_service.spend_balance(
            session, user, price, f"Оплата тарифа {plan.name}"
        )
        if not ok:
            await cb.answer("Недостаточно средств на балансе", show_alert=True)
            return
        if promo:
            await mark_promo_used(session, promo)

        try:
            sub = await create_subscription(
                session,
                get_remnawave(),
                user,
                plan=plan,
                duration_days=plan.duration_days,
                traffic_gb=plan.traffic_gb,
                devices_limit=plan.devices_limit,
                paid_amount=price,
            )
        except Exception as exc:  # noqa: BLE001
            await cb.answer(f"Ошибка активации: {exc}", show_alert=True)
            return
        await state.clear()
        await cb.message.answer("✅ Оплата с баланса прошла успешно.")
        await send_subscription_config(cb.bot, user, sub)
    await cb.answer()


@router.callback_query(
    F.data.startswith("pay:"), StateFilter(PurchaseFlow.choosing_payment)
)
async def cb_pay_provider(cb: CallbackQuery, state: FSMContext) -> None:
    provider_name = cb.data.split(":", 1)[1]
    provider = get_payments().get(provider_name)
    if provider is None:
        await cb.answer("Платёжный метод недоступен", show_alert=True)
        return

    async with session_scope() as session:
        user = await get_or_create_user(
            session, cb.from_user.id, cb.from_user.username
        )
        data = await state.get_data()
        plan = await session.get(Plan, int(data["plan_id"]))
        promo_code = data.get("promo_code")
        promo = await validate_promo(session, promo_code) if promo_code else None
        price = plan.price
        if promo:
            price, _ = compute_discount(plan.price, promo)

        balance = int(user.balance or 0)
        balance_used = balance if 0 < balance < price else 0
        invoice_amount = price - balance_used

        snapshot = {
            "plan_id": plan.id,
            "promo_code": promo_code,
            "duration_days": plan.duration_days,
            "traffic_gb": plan.traffic_gb,
            "devices_limit": plan.devices_limit,
            "balance_used": balance_used,
            "total": price,
            "is_trial": False,
        }
        payment = Payment(
            user_id=user.id,
            provider=provider_name,
            amount=invoice_amount,
            currency=settings.currency,
            status="pending",
            plan_id=plan.id,
            raw_payload=snapshot,
        )
        session.add(payment)
        await session.flush()

        try:
            invoice = await provider.create_invoice(
                amount=invoice_amount,
                currency=settings.currency,
                description=f"VPN: {plan.name}",
                metadata={"payment_id": str(payment.id)},
            )
        except Exception as exc:  # noqa: BLE001
            await session.delete(payment)
            await cb.answer(f"Ошибка создания счёта: {exc}", show_alert=True)
            return

        payment.provider_payment_id = invoice.provider_payment_id
        await state.clear()

        kb = InlineKeyboardBuilder()
        if invoice.pay_url:
            kb.button(text="💳 Оплатить", url=invoice.pay_url)
        await cb.message.edit_text(
            f"Счёт создан. К оплате: <b>{fmt_money(invoice_amount)}</b>.\n"
            "После оплаты подписка активируется автоматически.",
            parse_mode="HTML",
            reply_markup=kb.as_markup() if invoice.pay_url else None,
        )
    await cb.answer()
