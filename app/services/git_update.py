"""Проверка и применение git-обновлений (если репозиторий доступен в контейнере)."""
from __future__ import annotations

import asyncio
import os

# В Docker WORKDIR=/app, в dev — корень репозитория (bot/).
REPO_DIR = os.getcwd()


async def _run(*cmd: str) -> str:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=REPO_DIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await proc.communicate()
        return out.decode(errors="replace").strip()
    except FileNotFoundError:
        return ""


async def current_commit() -> str:
    sha = await _run("git", "rev-parse", "--short", "HEAD")
    return sha or "unknown"


async def check_updates() -> dict:
    """Вернуть {'ok', 'behind', 'ahead', 'error'}."""
    await _run("git", "fetch", "origin")
    behind = await _run("git", "rev-list", "--count", "HEAD..@{u}")
    ahead = await _run("git", "rev-list", "--count", "@{u}..HEAD")
    if behind == "" and ahead == "":
        return {
            "ok": False,
            "behind": 0,
            "ahead": 0,
            "error": "нет доступа к git/remote",
        }
    return {
        "ok": True,
        "behind": int(behind or 0),
        "ahead": int(ahead or 0),
        "error": "",
    }


async def git_pull() -> str:
    return await _run("git", "pull", "--ff-only")


def restart() -> None:
    """Перезапустить процесс (Docker restart: unless-stopped поднимет заново)."""
    os._exit(0)


def _marker_path() -> str:
    return os.path.join(REPO_DIR, "data", ".update_pending")


def mark_update_pending() -> None:
    path = _marker_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("1")


def has_update_marker() -> bool:
    return os.path.exists(_marker_path())


async def clear_update_marker() -> None:
    path = _marker_path()
    if os.path.exists(path):
        os.remove(path)


async def notify_update_complete(bot) -> None:
    """При старте: сообщить админам, что обновление завершено."""
    if not has_update_marker():
        return
    from app.config import settings

    sha = await current_commit()
    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(
                admin_id,
                f"✅ Обновление завершено.\nТекущая версия: <code>{sha}</code>",
                parse_mode="HTML",
            )
        except Exception:  # noqa: BLE001
            continue
    await clear_update_marker()
