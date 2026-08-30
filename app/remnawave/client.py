"""HTTP-клиент панели Remnawave 2.7.x.

Авторизация: POST /api/auth/login -> JWT (поле accessToken), далее
Authorization: Bearer. При 401 токен обновляется автоматически.

ВАЖНО: точные имена полей (shortUuid vs uuid, accessToken, hwidDeviceLimit)
сверяйте со Swagger конкретной панели (``{base}/docs``). Клиент написан
с расчётом на Remnawave 2.7.x, но допускает альтернативные имена.
"""
from __future__ import annotations

import secrets
from typing import Any

import httpx


class RemnawaveError(Exception):
    """Ошибка при обращении к панели Remnawave."""


def _first(data: dict, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return default


class RemnawaveClient:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        sub_url: str | None = None,
        api_token: str | None = None,
        node_uuid: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.sub_url = (sub_url or self.base_url).rstrip("/")
        self.username = username
        self.password = password
        self.api_token = api_token or None
        self.node_uuid = node_uuid or None
        self._token: str | None = None
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(30.0))

    def set_api_token(self, token: str | None) -> None:
        """Задать/сбросить статический API-токен (из админки)."""
        self.api_token = token or None

    def set_node_uuid(self, node_uuid: str | None) -> None:
        """Задать/сбросить UUID ноды, на которой выдавать пользователей."""
        self.node_uuid = node_uuid or None

    async def close(self) -> None:
        await self._http.aclose()

    async def login(self) -> str:
        resp = await self._http.post(
            f"{self.base_url}/api/auth/login",
            json={"username": self.username, "password": self.password},
        )
        if resp.status_code >= 400:
            raise RemnawaveError(
                f"login failed ({resp.status_code}): {resp.text[:200]}"
            )
        data = resp.json()
        self._token = _first(
            data, "accessToken", "access_token", "token", "jwt"
        )
        if not self._token:
            raise RemnawaveError(
                f"no access token in login response, keys={list(data)}"
            )
        return self._token

    async def _headers(self) -> dict:
        if self.api_token:
            return {"Authorization": f"Bearer {self.api_token}"}
        if not self._token:
            await self.login()
        return {"Authorization": f"Bearer {self._token}"}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        retry: bool = True,
    ) -> Any:
        headers = await self._headers()
        resp = await self._http.request(
            method, f"{self.base_url}{path}", headers=headers, json=json
        )
        if resp.status_code == 401 and retry and not self.api_token:
            await self.login()
            return await self._request(method, path, json=json, retry=False)
        if resp.status_code >= 400:
            raise RemnawaveError(
                f"{method} {path} -> {resp.status_code}: {resp.text[:300]}"
            )
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    @staticmethod
    def _as_items(data: Any) -> list[dict]:
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("items", "response", "data", "users", "inbounds", "hosts"):
                value = data.get(key)
                if isinstance(value, list):
                    return value
            return [data]
        return []

    # ----- inbounds / hosts -----
    async def get_inbounds(self) -> list[dict]:
        return self._as_items(await self._request("GET", "/api/inbounds"))

    async def get_hosts(self) -> list[dict]:
        return self._as_items(await self._request("GET", "/api/hosts"))

    # ----- users -----
    async def create_user(
        self,
        *,
        tg_id: int,
        traffic_limit_bytes: int,
        expire_at: str,
        devices_limit: int,
        email: str | None = None,
        username: str | None = None,
        short_uuid: str | None = None,
        node_uuid: str | None = None,
    ) -> dict:
        short_uuid = short_uuid or secrets.token_hex(4)
        payload = {
            "shortUuid": short_uuid,
            "username": username or short_uuid,
            "tgId": str(tg_id),
            "email": email or f"tg{tg_id}@bot.local",
            "expireAt": expire_at,
            "trafficLimitBytes": int(traffic_limit_bytes),
            "hwidDeviceLimit": int(devices_limit),
            "status": "ACTIVE",
        }
        target_node = node_uuid or self.node_uuid
        if target_node:
            payload["nodeUuid"] = target_node
        return await self._request("POST", "/api/users", json=payload)

    async def get_user(self, short_uuid: str) -> dict:
        return await self._request("GET", f"/api/users/{short_uuid}")

    async def get_users(self) -> list[dict]:
        return self._as_items(await self._request("GET", "/api/users"))

    async def update_user(self, short_uuid: str, **fields: Any) -> dict:
        return await self._request(
            "PATCH", f"/api/users/{short_uuid}", json=fields
        )

    async def delete_user(self, short_uuid: str) -> Any:
        return await self._request("DELETE", f"/api/users/{short_uuid}")

    async def get_user_devices(self, short_uuid: str) -> list[dict]:
        data = await self._request(
            "GET", f"/api/users/{short_uuid}/devices"
        )
        return self._as_items(data)

    async def disable_user(self, short_uuid: str) -> dict:
        return await self.update_user(short_uuid, status="DISABLED")

    async def set_device_limit(self, short_uuid: str, devices_limit: int) -> dict:
        return await self.update_user(
            short_uuid, hwidDeviceLimit=int(devices_limit)
        )

    # ----- подписка / конфиг -----
    async def get_subscription(self, short_uuid: str) -> list[str]:
        """Вернуть vless:// ссылки подписки пользователя."""
        resp = await self._http.get(
            f"{self.sub_url}/sub/{short_uuid}",
            headers={"Accept": "application/json"},
        )
        if resp.status_code >= 400:
            raise RemnawaveError(
                f"subscription fetch failed ({resp.status_code}): {resp.text[:200]}"
            )
        try:
            data = resp.json()
        except Exception:
            data = resp.text
        return extract_vless_links(data)


def extract_vless_links(data: Any) -> list[str]:
    """Достать все vless:// ссылки из произвольного ответа подписки."""
    found: list[str] = []

    def _walk(value: Any) -> None:
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("vless://"):
                found.append(value)
            return
        if isinstance(value, list):
            for item in value:
                _walk(item)
            return
        if isinstance(value, dict):
            for item in value.values():
                _walk(item)

    _walk(data)
    seen: set[str] = set()
    result: list[str] = []
    for link in found:
        if link not in seen:
            seen.add(link)
            result.append(link)
    return result
