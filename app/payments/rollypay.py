"""RollyPay (агрегатор) — заготовка под документацию провайдера.

Создание счёта: POST {api_url}/invoices с Authorization: Bearer <api_key>.
Вебхук: JSON с id/status/amount, подпись HMAC-SHA256 (secret).
Перед использованием сверьте поля с документацией RollyPay.
"""
from __future__ import annotations

import hashlib
import hmac

import httpx

from app.payments.base import Invoice, PaymentProvider, WebhookResult


class RollyPayProvider(PaymentProvider):
    name = "rollypay"

    def __init__(self, api_url: str, api_key: str, secret: str) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.secret = secret

    async def create_invoice(
        self,
        *,
        amount: int,
        currency: str,
        description: str,
        metadata: dict | None = None,
    ) -> Invoice:
        body = {
            "amount": amount,
            "currency": currency,
            "description": description[:128],
            "metadata": metadata or {},
        }
        async with httpx.AsyncClient(timeout=20) as http:
            resp = await http.post(
                f"{self.api_url}/invoices",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
        result = data.get("data") or data
        pay_url = (
            result.get("pay_url")
            or result.get("payment_url")
            or result.get("url")
        )
        provider_id = str(
            result.get("id") or result.get("invoice_id") or result.get("payment_id")
        )
        return Invoice(provider_payment_id=provider_id, pay_url=pay_url)

    def parse_webhook(self, payload: dict) -> WebhookResult:
        status_map = {
            "success": "succeeded",
            "succeeded": "succeeded",
            "paid": "succeeded",
            "failed": "failed",
            "canceled": "canceled",
        }
        status = status_map.get(payload.get("status"), "pending")
        return WebhookResult(
            provider_payment_id=str(
                payload.get("id")
                or payload.get("invoice_id")
                or payload.get("payment_id")
                or ""
            ),
            status=status,
            amount=int(payload.get("amount", 0) or 0),
            currency=str(payload.get("currency", "")),
        )

    def verify_signature(self, raw_body: str, headers: dict) -> bool:
        signature = headers.get("x-signature") or headers.get("signature") or ""
        expected = hmac.new(
            self.secret.encode(), raw_body.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
