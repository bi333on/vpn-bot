"""Бизнес-логика подписок: выдача, продление, отключение, конфиг."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Plan, Subscription, User
from app.remnawave.client import RemnawaveClient
from app.services.config_builder import build_vless, resolve_connection
from app.utils import gb_to_bytes


def _unwrap(data: dict) -> dict:
    if isinstance(data, dict) and isinstance(data.get("response"), dict):
        return data["response"]
    return data


async def build_config_link(
    client: RemnawaveClient,
    user_uuid: str,
    short_uuid: str,
    remark: str = "VPN",
) -> str:
    """Получить vless:// ссылку: сначала из подписки Remnawave, иначе собрать."""
    try:
        links = await client.get_subscription(short_uuid)
        if links:
            return links[0]
    except Exception:
        pass
    inbounds = await client.get_inbounds()
    hosts = await client.get_hosts()
    conn = resolve_connection(inbounds, hosts, settings.remnawave_inbound_tag)
    return build_vless(
        user_uuid,
        conn["address"],
        conn["port"],
        conn["public_key"],
        conn["short_id"],
        conn["sni"],
        conn["flow"],
        remark,
    )


async def create_subscription(
    session: AsyncSession,
    client: RemnawaveClient,
    user: User,
    *,
    plan: Plan | None,
    duration_days: int,
    traffic_gb: int,
    devices_limit: int,
    is_trial: bool = False,
    payment_id: int | None = None,
    paid_amount: int = 0,
    remark: str = "VPN",
) -> Subscription:
    """Создать пользователя в Remnawave и локальную подписку."""
    expires_at = datetime.now(timezone.utc) + timedelta(days=duration_days)
    traffic_limit_bytes = gb_to_bytes(traffic_gb)

    short_uuid = secrets.token_hex(4)
    data = await client.create_user(
        tg_id=user.telegram_id,
        traffic_limit_bytes=traffic_limit_bytes,
        expire_at=expires_at.isoformat(),
        devices_limit=devices_limit,
        short_uuid=short_uuid,
    )
    data = _unwrap(data)
    remnawave_uuid = str(data.get("uuid") or "")
    resp_short = data.get("shortUuid") or data.get("short_uuid")
    if resp_short:
        short_uuid = str(resp_short)

    config_link = None
    try:
        config_link = await build_config_link(
            client, remnawave_uuid or "", short_uuid, remark
        )
    except Exception:
        config_link = None

    sub = Subscription(
        user_id=user.id,
        plan_id=plan.id if plan else None,
        remnawave_uuid=remnawave_uuid,
        remnawave_short_uuid=short_uuid,
        status="active",
        traffic_limit_bytes=traffic_limit_bytes,
        expires_at=expires_at,
        paid_amount=paid_amount,
        payment_id=payment_id,
        is_trial=is_trial,
        devices_limit=devices_limit,
        config_link=config_link,
    )
    session.add(sub)
    await session.flush()
    return sub


async def extend_subscription(
    session: AsyncSession,
    client: RemnawaveClient,
    sub: Subscription,
    *,
    duration_days: int,
    traffic_gb: int | None = None,
    devices_limit: int | None = None,
) -> None:
    """Продлить подписку (дата + опционально трафик/лимит устройств)."""
    now = datetime.now(timezone.utc)
    base = sub.expires_at if sub.expires_at and sub.expires_at > now else now
    new_expires = base + timedelta(days=duration_days)
    fields: dict = {"expireAt": new_expires.isoformat(), "status": "ACTIVE"}
    if traffic_gb is not None:
        sub.traffic_limit_bytes = gb_to_bytes(traffic_gb)
        fields["trafficLimitBytes"] = sub.traffic_limit_bytes
    if devices_limit is not None:
        sub.devices_limit = int(devices_limit)
        fields["hwidDeviceLimit"] = int(devices_limit)
    await client.update_user(sub.remnawave_short_uuid, **fields)
    sub.expires_at = new_expires
    sub.status = "active"


async def set_device_limit(
    session: AsyncSession,
    client: RemnawaveClient,
    sub: Subscription,
    devices_limit: int,
) -> None:
    """Сменить лимит устройств без продления (пересчёт в Remnawave)."""
    await client.set_device_limit(sub.remnawave_short_uuid, devices_limit)
    sub.devices_limit = int(devices_limit)


async def disable_subscription(
    session: AsyncSession,
    client: RemnawaveClient,
    sub: Subscription,
) -> None:
    await client.disable_user(sub.remnawave_short_uuid)
    sub.status = "disabled"


async def delete_subscription(
    session: AsyncSession,
    client: RemnawaveClient,
    sub: Subscription,
) -> None:
    await client.delete_user(sub.remnawave_short_uuid)
    await session.delete(sub)
