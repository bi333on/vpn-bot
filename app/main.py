"""Точка входа: webhook (aiohttp) + платёжные вебхуки, либо long polling."""
from __future__ import annotations

import asyncio
import json
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web
from sqlalchemy import select

from app.config import settings
from app.context import close_external, get_payments
from app.db.engine import dispose_engine, init_db, session_scope
from app.db.models import Payment
from app.handlers import register_handlers
from app.scheduler.jobs import start_scheduler
from app.services.messaging import send_subscription_config
from app.services.payment_flow import finalize_payment
from app.services.remnawave_config import load_remnawave_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_bot() -> Bot:
    return Bot(token=settings.bot_token)


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    register_handlers(dp)
    return dp


async def payment_webhook(request: web.Request) -> web.Response:
    provider_name = request.match_info["provider"]
    provider = get_payments().get(provider_name)
    if provider is None:
        return web.json_response({"error": "unknown provider"}, status=404)

    raw = await request.read()
    body_text = raw.decode("utf-8")
    if not provider.verify_signature(body_text, dict(request.headers)):
        return web.json_response({"error": "bad signature"}, status=403)

    try:
        payload = json.loads(body_text)
    except json.JSONDecodeError:
        return web.json_response({"error": "bad json"}, status=400)

    result = provider.parse_webhook(payload)

    status = "ignored"
    sub = None
    user = None
    async with session_scope() as session:
        payment = (
            await session.execute(
                select(Payment).where(
                    Payment.provider_payment_id == result.provider_payment_id
                )
            )
        ).scalar_one_or_none()
        if payment is None:
            return web.json_response({"error": "unknown payment"}, status=404)

        if result.status == "succeeded":
            status, sub, user = await finalize_payment(session, payment)
        else:
            payment.status = result.status

    if status == "succeeded" and sub is not None and user is not None:
        try:
            await send_subscription_config(request.app["bot"], user, sub)
        except Exception:  # noqa: BLE001
            logger.exception("failed to send config after payment")

    return web.json_response({"ok": True})


async def health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def run_polling() -> None:
    bot = build_bot()
    dp = build_dispatcher()
    await init_db()
    await load_remnawave_settings()
    start_scheduler(bot)
    try:
        await dp.start_polling(bot, drop_pending_updates=True)
    finally:
        await bot.session.close()
        await close_external()
        await dispose_engine()


async def run_webhook() -> None:
    bot = build_bot()
    dp = build_dispatcher()
    await init_db()
    await load_remnawave_settings()

    app = web.Application()
    app["bot"] = bot
    app["dp"] = dp
    app.router.add_post("/payments/{provider}", payment_webhook)
    app.router.add_get("/health", health)

    handler = SimpleRequestHandler(
        dispatcher=dp, bot=bot, secret_token=settings.webhook_secret
    )
    app.router.add_post(settings.webhook_path, handler.handle)

    await bot.set_webhook(
        url=f"{settings.webhook_host}{settings.webhook_path}",
        secret_token=settings.webhook_secret,
        drop_pending_updates=True,
    )
    start_scheduler(bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=8000)
    await site.start()
    logger.info("webhook server started on :8000")

    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
        await bot.session.close()
        await close_external()
        await dispose_engine()


def main() -> None:
    if settings.polling_mode:
        asyncio.run(run_polling())
    else:
        asyncio.run(run_webhook())


if __name__ == "__main__":
    main()
