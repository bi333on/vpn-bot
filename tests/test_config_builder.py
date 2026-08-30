from app.remnawave.client import extract_vless_links
from app.services.config_builder import build_vless, resolve_connection


def test_build_vless():
    link = build_vless(
        "uuid-1", "vpn.example.com", 443, "PBK", "abcd", "sni.example.com"
    )
    assert link.startswith("vless://uuid-1@vpn.example.com:443?")
    assert "security=reality" in link
    assert "pbk=PBK" in link
    assert "sni=sni.example.com" in link
    assert "sid=abcd" in link
    assert "flow=xtls-rprx-vision" in link
    assert "spx=%2F" in link


def test_resolve_connection():
    inbounds = [
        {
            "tag": "reality",
            "type": "reality",
            "port": 443,
            "realityPublicKey": "PBK",
            "settings": {
                "flow": "xtls-rprx-vision",
                "realitySettings": {
                    "serverNames": ["sni.com"],
                    "shortIds": ["ab12"],
                },
            },
        }
    ]
    hosts = [{"address": "vpn.host", "port": 443}]
    conn = resolve_connection(inbounds, hosts)
    assert conn["address"] == "vpn.host"
    assert conn["port"] == 443
    assert conn["sni"] == "sni.com"
    assert conn["short_id"] == "ab12"
    assert conn["public_key"] == "PBK"


def test_extract_vless_links():
    data = {"links": ["vless://a@b:1?#x", "vless://c@d:2?#y"]}
    assert extract_vless_links(data) == [
        "vless://a@b:1?#x",
        "vless://c@d:2?#y",
    ]


def test_extract_vless_links_dedup():
    data = {"links": ["vless://a@b:1?#x", "vless://a@b:1?#x"]}
    assert extract_vless_links(data) == ["vless://a@b:1?#x"]
