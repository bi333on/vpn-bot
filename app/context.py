"""Ленивые синглтоны внешних зависимостей (Remnawave, платёжки)."""
from __future__ import annotations

from app.config import settings
from app.payments.manager import PaymentManager
from app.remnawave.client import RemnawaveClient

_remnawave: RemnawaveClient | None = None
_payments: PaymentManager | None = None


def get_remnawave() -> RemnawaveClient:
    global _remnawave
    if _remnawave is None:
        _remnawave = RemnawaveClient(
            settings.remnawave_api_url,
            settings.remnawave_username,
            settings.remnawave_password,
            settings.sub_url,
            settings.remnawave_api_token or None,
            settings.remnawave_node_uuid or None,
            settings.remnawave_node_field or "nodeUuid",
        )
    return _remnawave


def get_payments() -> PaymentManager:
    global _payments
    if _payments is None:
        _payments = PaymentManager.build()
    return _payments


async def close_external() -> None:
    global _remnawave
    if _remnawave is not None:
        await _remnawave.close()
        _remnawave = None
