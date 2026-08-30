"""ЮKassa (карты/СБП). Суммы — в копейках внутри бота, SDK — в рублях."""
from __future__ import annotations

import asyncio

import yookassa
from yookassa import Payment

from app.payments.base import Invoice, PaymentProvider, WebhookResult

_STATUS_MAP = {
    "succeeded": "succeeded",
    "canceled": "canceled",
    "pending": "pending",
    "waiting_for_capture": "pending",
}


class YooKassaProvider(PaymentProvider):
    name = "yookassa"

    def __init__(self, shop_id: str, secret_key: str) -> None:
        yookassa.Configuration.account_id = shop_id
        yookassa.Configuration.secret_key = secret_key

    async def create_invoice(
        self,
        *,
        amount: int,
        currency: str,
        description: str,
        metadata: dict | None = None,
    ) -> Invoice:
        payload = {
            "amount": {"value": f"{amount / 100:.2f}", "currency": currency},
            "capture": True,
            "confirmation": {"type": "redirect"},
            "description": description[:128],
            "metadata": metadata or {},
        }

        def _create() -> Payment:
            return Payment.create(payload)

        payment = await asyncio.to_thread(_create)
        pay_url = (
            payment.confirmation.confirmation_url if payment.confirmation else None
        )
        return Invoice(provider_payment_id=payment.id, pay_url=pay_url)

    def parse_webhook(self, payload: dict) -> WebhookResult:
        obj = payload.get("object", payload)
        status = _STATUS_MAP.get(obj.get("status"), "pending")
        amount_obj = obj.get("amount") or {}
        amount = 0
        try:
            amount = int(round(float(amount_obj.get("value", "0")) * 100))
        except (TypeError, ValueError):
            amount = 0
        return WebhookResult(
            provider_payment_id=str(obj.get("id", "")),
            status=status,
            amount=amount,
            currency=str(amount_obj.get("currency", "")),
        )
