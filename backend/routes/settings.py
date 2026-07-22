"""Villanyan-Agent 3.0 — Settings routes (read/write .env at runtime)."""
import os
import pathlib
import re

from fastapi import APIRouter, Depends, HTTPException

from backend.core.models import User
from backend.core.security import get_current_user

router = APIRouter(prefix="/api/settings", tags=["settings"])

ENV_FILE = pathlib.Path(__file__).parent.parent.parent / ".env"

EDITABLE_KEYS = frozenset({
    "GEMINI_API_KEY", "OPENAI_API_KEY", "OLLAMA_API_URL",
    "OLLAMA_MODEL", "DEBUG", "BCRYPT_ROUNDS",
    "ACCESS_TOKEN_EXPIRE_MINUTES", "REFRESH_TOKEN_EXPIRE_DAYS",
})


def _read_env() -> dict[str, str]:
    result = {}
    if not ENV_FILE.exists():
        return result
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        result[k.strip()] = v.strip()
    return result


def _write_env_key(key: str, value: str) -> None:
    if not ENV_FILE.exists():
        raise HTTPException(status_code=404, detail=".env not found")
    content = ENV_FILE.read_text()
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    if pattern.search(content):
        content = pattern.sub(f"{key}={value}", content)
    else:
        content += f"\n{key}={value}"
    ENV_FILE.write_text(content)


@router.get("")
async def get_settings(user: User = Depends(get_current_user)):
    """Read editable .env settings (safe keys only)."""
    env = _read_env()
    return {k: env.get(k, "") for k in sorted(EDITABLE_KEYS)}


@router.patch("")
async def update_settings(body: dict, user: User = Depends(get_current_user)):
    """Update editable .env settings."""
    for key, value in body.items():
        if key not in EDITABLE_KEYS:
            raise HTTPException(status_code=400, detail=f"Key {key!r} not editable")
        _write_env_key(key, str(value))
    return {"updated": list(body.keys()), "status": "saved"}
