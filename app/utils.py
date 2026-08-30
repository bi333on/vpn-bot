"""Вспомогательные функции."""
from __future__ import annotations

import secrets
import string

from app.config import settings


def fmt_money(kopecks: int) -> str:
    """Отформатировать сумму в копейках/центах (RUB)."""
    sign = "-" if kopecks < 0 else ""
    kopecks = abs(int(kopecks))
    return f"{sign}{kopecks // 100}.{kopecks % 100:02d} ₽"


def gb_to_bytes(gb: int) -> int:
    return int(gb) * 1024 * 1024 * 1024


def fmt_bytes(num_bytes: int) -> str:
    if num_bytes is None:
        return "—"
    gb = int(num_bytes) / (1024 * 1024 * 1024)
    if gb >= 1:
        return f"{gb:.2f} ГБ"
    mb = int(num_bytes) / (1024 * 1024)
    return f"{mb:.0f} МБ"


def generate_referral_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(10))
