"""Конфигурация приложения (pydantic-settings)."""
from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Telegram ---
    bot_token: str = Field(default="", alias="BOT_TOKEN")
    admin_ids: Annotated[list[int], NoDecode] = Field(
        default_factory=list, alias="ADMIN_IDS"
    )

    # --- Storage ---
    database_url: str = Field(
        default="sqlite+aiosqlite:///bot.db", alias="DATABASE_URL"
    )

    # --- Polling / webhook ---
    polling_mode: bool = Field(default=True, alias="POLLING_MODE")
    webhook_host: str = Field(default="", alias="WEBHOOK_HOST")
    webhook_path: str = Field(default="/telegram", alias="WEBHOOK_PATH")
    webhook_secret: Optional[str] = Field(
        default=None, alias="WEBHOOK_SECRET_TOKEN"
    )
    payments_base_url: str = Field(default="", alias="PAYMENTS_BASE_URL")

    # --- Remnawave ---
    remnawave_api_url: str = Field(default="", alias="REMNAWAVE_API_URL")
    remnawave_sub_url: str = Field(default="", alias="REMNAWAVE_SUB_URL")
    remnawave_username: str = Field(default="", alias="REMNAWAVE_USERNAME")
    remnawave_password: str = Field(default="", alias="REMNAWAVE_PASSWORD")
    remnawave_api_token: str = Field(default="", alias="REMNAWAVE_API_TOKEN")
    remnawave_node_uuid: str = Field(default="", alias="REMNAWAVE_NODE_UUID")
    remnawave_node_field: str = Field(
        default="nodeUuid", alias="REMNAWAVE_NODE_FIELD"
    )
    remnawave_inbound_tag: str = Field(default="", alias="REMNAWAVE_INBOUND_TAG")

    # --- Деньги / рефералка ---
    currency: str = Field(default="RUB", alias="CURRENCY")
    referral_percent: int = Field(default=10, alias="REFERRAL_PERCENT")
    support_link: str = Field(default="https://t.me/support", alias="SUPPORT_LINK")
    channel_link: str = Field(default="", alias="CHANNEL_LINK")
    web_link: str = Field(default="", alias="WEB_CABINET_LINK")

    # --- Trial ---
    trial_enabled: bool = Field(default=True, alias="TRIAL_ENABLED")
    trial_days: int = Field(default=3, alias="TRIAL_DAYS")
    trial_gb: int = Field(default=5, alias="TRIAL_GB")
    trial_devices: int = Field(default=1, alias="TRIAL_DEVICES")

    # --- ЮKassa ---
    yookassa_enabled: bool = Field(default=False, alias="YOOKASSA_ENABLED")
    yookassa_shop_id: str = Field(default="", alias="YOOKASSA_SHOP_ID")
    yookassa_secret_key: str = Field(default="", alias="YOOKASSA_SECRET_KEY")

    # --- CryptoBot (Crypto Pay) ---
    cryptobot_enabled: bool = Field(default=False, alias="CRYPTOBOT_ENABLED")
    cryptobot_api_token: str = Field(default="", alias="CRYPTOBOT_API_TOKEN")
    cryptobot_webhook_secret: str = Field(
        default="", alias="CRYPTOBOT_WEBHOOK_SECRET"
    )

    # --- RollyPay ---
    rollypay_enabled: bool = Field(default=False, alias="ROLLYPAY_ENABLED")
    rollypay_api_url: str = Field(
        default="https://api.rollypay.com", alias="ROLLYPAY_API_URL"
    )
    rollypay_api_key: str = Field(default="", alias="ROLLYPAY_API_KEY")
    rollypay_secret: str = Field(default="", alias="ROLLYPAY_SECRET")

    # --- Уведомления ---
    notify_before_days: Annotated[list[int], NoDecode] = Field(
        default_factory=lambda: [3, 1], alias="NOTIFY_BEFORE_DAYS"
    )
    notify_traffic_percent: int = Field(
        default=80, alias="NOTIFY_TRAFFIC_PERCENT"
    )

    @field_validator("admin_ids", "notify_before_days", mode="before")
    @classmethod
    def _split_comma_separated(cls, value):
        if isinstance(value, str):
            return [int(x.strip()) for x in value.split(",") if x.strip()]
        return value

    @property
    def sub_url(self) -> str:
        return self.remnawave_sub_url or self.remnawave_api_url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
