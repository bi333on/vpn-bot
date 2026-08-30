"""Сборка vless:// конфига из данных Remnawave (чистые функции)."""
from __future__ import annotations

from urllib.parse import quote


def build_vless(
    uuid: str,
    address: str,
    port: int,
    public_key: str,
    short_id: str,
    sni: str,
    flow: str = "xtls-rprx-vision",
    remark: str = "VPN",
) -> str:
    """Собрать ссылку vless+reality (tcp)."""
    params = [
        ("type", "tcp"),
        ("security", "reality"),
        ("pbk", public_key),
        ("fp", "chrome"),
        ("sni", sni),
        ("sid", short_id),
        ("spx", "/"),
    ]
    if flow:
        params.append(("flow", flow))
    query = "&".join(
        f"{key}={quote(str(value), safe='')}" for key, value in params
    )
    return f"vless://{uuid}@{address}:{port}?{query}#{quote(remark, safe='')}"


def _pick_reality_inbound(
    inbounds: list[dict],
    preferred_tag: str = "",
    preferred_node_uuid: str = "",
) -> dict:
    if not inbounds:
        raise ValueError("no inbounds configured")
    candidates = inbounds
    if preferred_node_uuid:
        filtered = [
            i
            for i in inbounds
            if i.get("nodeUuid") == preferred_node_uuid
            or i.get("node_uuid") == preferred_node_uuid
        ]
        if filtered:
            candidates = filtered
    if preferred_tag:
        for item in candidates:
            if item.get("tag") == preferred_tag:
                return item
    for item in candidates:
        kind = str(item.get("type") or item.get("protocol") or "").lower()
        if kind in ("reality", "vless") and (
            str(item.get("security") or "").lower() == "reality"
            or kind == "reality"
        ):
            return item
    return candidates[0]


def resolve_connection(
    inbounds: list[dict],
    hosts: list[dict],
    preferred_tag: str = "",
    preferred_node_uuid: str = "",
) -> dict:
    """Извлечь параметры подключения (address/port/pbk/sid/sni/flow)."""
    inbound = _pick_reality_inbound(inbounds, preferred_tag, preferred_node_uuid)

    host_list = hosts
    if preferred_node_uuid:
        filtered_hosts = [
            h
            for h in hosts
            if h.get("nodeUuid") == preferred_node_uuid
            or h.get("node_uuid") == preferred_node_uuid
        ]
        if filtered_hosts:
            host_list = filtered_hosts
    host = host_list[0] if host_list else {}
    address = str(
        host.get("address")
        or host.get("server")
        or host.get("host")
        or inbound.get("address")
        or ""
    )
    port = int(
        host.get("port")
        or inbound.get("port")
        or inbound.get("listenPort")
        or 443
    )

    settings = inbound.get("settings") or {}
    reality = settings.get("realitySettings") or inbound.get("realitySettings") or {}

    server_names = reality.get("serverNames") or []
    sni = str(server_names[0]) if server_names else ""
    if not sni:
        dest = str(reality.get("dest") or "")
        sni = dest.split(":")[0] if dest else ""

    short_ids = reality.get("shortIds") or []
    short_id = str(short_ids[0]) if short_ids else ""

    public_key = str(
        inbound.get("realityPublicKey")
        or reality.get("publicKey")
        or reality.get("public_key")
        or host.get("publicKey")
        or host.get("public_key")
        or ""
    )

    flow = str(
        settings.get("flow")
        or (settings.get("vless") or {}).get("flow")
        or reality.get("flow")
        or "xtls-rprx-vision"
    )

    return {
        "address": address,
        "port": port,
        "public_key": public_key,
        "short_id": short_id,
        "sni": sni,
        "flow": flow,
    }
