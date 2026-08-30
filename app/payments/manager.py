"""Реестр платёжных провайдеров."""
from __future__ import annotations

from app.config import settings
from app.payments.base import PaymentProvider
from app.payments.cryptobot import CryptoBotProvider
from app.payments.rollypay import RollyPayProvider
from app.payments.yookassa import YooKassaProvider


class PaymentManager:
    def __init__(self, providers: dict[str, PaymentProvider]) -> None:
        self.providers = providers

    @classmethod
    def build(cls) -> "PaymentManager":
        providers: dict[str, PaymentProvider] = {}
        if settings.yookassa_enabled and settings.yookassa_shop_id:
            providers["yookassa"] = YooKassaProvider(
                settings.yookassa_shop_id, settings.yookassa_secret_key
            )
        if settings.cryptobot_enabled and settings.cryptobot_api_token:
            providers["cryptobot"] = CryptoBotProvider(
                settings.cryptobot_api_token, settings.cryptobot_webhook_secret
            )
        if settings.rollypay_enabled and settings.rollypay_api_key:
            providers["rollypay"] = RollyPayProvider(
                settings.rollypay_api_url,
                settings.rollypay_api_key,
                settings.rollypay_secret,
            )
        return cls(providers)

    def get(self, name: str) -> PaymentProvider | None:
        return self.providers.get(name)

    def names(self) -> list[str]:
        return list(self.providers.keys())

    @property
    def is_empty(self) -> bool:
        return not self.providers
