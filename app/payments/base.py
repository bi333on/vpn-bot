"""Абстракция платёжного провайдера."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Invoice:
    provider_payment_id: str
    pay_url: str | None = None


@dataclass
class WebhookResult:
    provider_payment_id: str
    status: str  # succeeded | failed | canceled | pending
    amount: int = 0  # в минорных единицах; 0 — доверять сумме из БД
    currency: str = ""


class PaymentProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def create_invoice(
        self,
        *,
        amount: int,
        currency: str,
        description: str,
        metadata: dict | None = None,
    ) -> Invoice:
        """Создать счёт на оплату. amount — в минорных единицах."""

    @abstractmethod
    def parse_webhook(self, payload: dict) -> WebhookResult:
        """Разобрать тело вебхука в нормализованный результат."""

    def verify_signature(self, raw_body: str, headers: dict) -> bool:
        """Проверить подпись вебхука. По умолчанию — доверяем."""
        return True
