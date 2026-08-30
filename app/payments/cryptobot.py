"""CryptoBot (Crypto Pay API, crypto). Счёт в USDT по курсу, вебхук с HMAC."""
from __future__ import annotations

import hashlib
import hmac

import httpx

from app.payments.base import Invoice, PaymentProvider, WebhookResult

_API_URL = "https://pay.crypt.bot"


class CryptoBotProvider(PaymentProvider):
    name = "cryptobot"

    def __init__(self, api_token: str, webhook_secret: str = "") -> None:
        self.api_token = api_token
        self.webhook_secret = webhook_secret or api_token

    def _headers(self) -> dict:
        return {"Crypto-Pay-API-Token": self.api_token}

    async def _usdt_rub_rate(self) -> float:
        async with httpx.AsyncClient(timeout=20) as http:
            resp = await http.get(
                f"{_API_URL}/api/getExchangeRates", headers=self._headers()
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                raise RuntimeError(f"getExchangeRates failed: {data}")
            for rate in data.get("result", []):
                if rate.get("source") == "USDT" and rate.get("target") == "RUB":
                    return float(rate.get("rate", 0))
        return 0.0

    async def create_invoice(
        self,
        *,
        amount: int,
        currency: str,
        description: str,
        metadata: dict | None = None,
    ) -> Invoice:
        if currency == "RUB":
            rate = await self._usdt_rub_rate()
            if rate <= 0:
                raise RuntimeError("cannot resolve USDT/RUB rate")
            usdt_amount = round((amount / 100) / rate, 2)
        else:
            usdt_amount = round(amount / 100, 2)

        body = {
            "asset": "USDT",
            "amount": f"{usdt_amount:.2f}",
            "description": description[:128],
            "payload": str((metadata or {}).get("payment_id", "")),
            "allow_anonymous": False,
        }
        async with httpx.AsyncClient(timeout=20) as http:
            resp = await http.post(
                f"{_API_URL}/api/createInvoice",
                headers=self._headers(),
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"createInvoice failed: {data}")
        result = data.get("result", {})
        return Invoice(
            provider_payment_id=str(result.get("invoice_id")),
            pay_url=result.get("pay_url") or result.get("bot_invoice_url"),
        )

    def parse_webhook(self, payload: dict) -> WebhookResult:
        inner = payload.get("payload") or {}
        status_map = {
            "paid": "succeeded",
            "failed": "failed",
            "expired": "canceled",
        }
        status = status_map.get(inner.get("status"), "pending")
        return WebhookResult(
            provider_payment_id=str(inner.get("invoice_id", "")),
            status=status,
            amount=0,
            currency="",
        )

    def verify_signature(self, raw_body: str, headers: dict) -> bool:
        signature = headers.get("crypto-pay-api-signature", "")
        expected = hmac.new(
            self.webhook_secret.encode(), raw_body.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
