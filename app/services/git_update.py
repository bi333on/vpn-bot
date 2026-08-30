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
