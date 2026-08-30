"""Проверка формирования запроса к Remnawave (в т.ч. hwidDeviceLimit)."""
from __future__ import annotations

import json

import httpx

from app.remnawave.client import RemnawaveClient


async def test_create_user_sends_hwid_device_limit():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={"uuid": "u1", "shortUuid": "abcd1234"})

    client = RemnawaveClient("https://panel.test", "admin", "secret")
    client._token = "tok"
    client._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    try:
        data = await client.create_user(
            tg_id=111,
            traffic_limit_bytes=50 * 1024**3,
            expire_at="2026-09-01T00:00:00+00:00",
            devices_limit=3,
        )
    finally:
        await client._http.aclose()

    assert captured["url"].endswith("/api/users")
    assert captured["json"]["hwidDeviceLimit"] == 3
    assert captured["json"]["trafficLimitBytes"] == 50 * 1024**3
    assert captured["json"]["tgId"] == "111"
    assert data["uuid"] == "u1"


async def test_set_device_limit_payload():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True})

    client = RemnawaveClient("https://panel.test", "admin", "secret")
    client._token = "tok"
    client._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    try:
        await client.set_device_limit("abcd1234", 5)
    finally:
        await client._http.aclose()

    assert captured["json"]["hwidDeviceLimit"] == 5
