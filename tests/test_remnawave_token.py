from __future__ import annotations

import json

import httpx

from app.remnawave.client import RemnawaveClient
from app.services.remnawave_config import (
    get_remnawave_api_token,
    get_remnawave_node_uuid,
    set_remnawave_api_token,
    set_remnawave_node_uuid,
)


async def test_api_token_auth_no_login():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"uuid": "u1", "shortUuid": "abcd"})

    client = RemnawaveClient("https://panel.test", "", "", api_token="SECRET")
    client._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        await client.create_user(
            tg_id=1,
            traffic_limit_bytes=1024,
            expire_at="2026-09-01T00:00:00+00:00",
            devices_limit=2,
        )
    finally:
        await client._http.aclose()

    assert captured["auth"] == "Bearer SECRET"


async def test_create_user_sends_node_uuid():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={"uuid": "u1", "shortUuid": "abcd"})

    client = RemnawaveClient("https://panel.test", "", "", node_uuid="NODE-1")
    client._token = "tok"
    client._http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        await client.create_user(
            tg_id=1,
            traffic_limit_bytes=1024,
            expire_at="2026-09-01T00:00:00+00:00",
            devices_limit=2,
        )
    finally:
        await client._http.aclose()

    assert captured["json"]["nodeUuid"] == "NODE-1"


async def test_remnawave_token_get_set(db_session):
    assert await get_remnawave_api_token(db_session) is None
    await set_remnawave_api_token(db_session, "TOK123")
    await db_session.flush()
    assert await get_remnawave_api_token(db_session) == "TOK123"


async def test_remnawave_node_get_set(db_session):
    assert await get_remnawave_node_uuid(db_session) is None
    await set_remnawave_node_uuid(db_session, "node-abc")
    await db_session.flush()
    assert await get_remnawave_node_uuid(db_session) == "node-abc"
