"""Villanyan-Agent 3.0 — Obsidian routes (vault integration)."""

import os
import pathlib
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.core.models import User
from backend.core.security import get_current_user

router = APIRouter(prefix="/api/obsidian", tags=["obsidian"])

OBSIDIAN_VAULT = pathlib.Path(os.path.expanduser("~/obsidian-vault"))
REMINDERS_FILE = OBSIDIAN_VAULT / "Hermes" / "Przypomnienia.md"


def _render_template(request: Request, template_name: str, **context):
    """Render Jinja2 template safely (workaround for jinja2 3.1.6 + starlette bug)."""
    env = request.app.state.templates.env
    tmpl = env.get_template(template_name)
    html = tmpl.render({"request": request, **context})
    from starlette.responses import HTMLResponse
    return HTMLResponse(html)


def _vault_exists() -> bool:
    return OBSIDIAN_VAULT.exists()


def _parse_reminders() -> list[dict]:
    """Parse Przypomnienia.md — simple markdown list parsing."""
    if not REMINDERS_FILE.exists():
        return []

    text = REMINDERS_FILE.read_text(encoding="utf-8")
    reminders = []
    for i, line in enumerate(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        # Support - [ ] task and - [x] task formats
        if line.startswith("- [ ]"):
            reminders.append({
                "id": i + 1,
                "text": line[5:].strip(),
                "done": False,
                "line": i + 1,
            })
        elif line.startswith("- [x]"):
            reminders.append({
                "id": i + 1,
                "text": line[5:].strip(),
                "done": True,
                "line": i + 1,
            })
        elif line.startswith("- "):
            reminders.append({
                "id": i + 1,
                "text": line[2:].strip(),
                "done": False,
                "line": i + 1,
            })
    return reminders


def _write_reminders(reminders: list[dict]) -> None:
    """Write reminders back to Przypomnienia.md."""
    REMINDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for r in reminders:
        if r["done"]:
            lines.append(f"- [x] {r['text']}")
        else:
            lines.append(f"- [ ] {r['text']}")
    REMINDERS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


class ReminderInput(BaseModel):
    text: str = Field(..., min_length=1)


@router.get("/status")
async def get_obsidian_status(
    user: User = Depends(get_current_user),
):
    """Check Obsidian vault status."""
    return {
        "vault_exists": _vault_exists(),
        "vault_path": str(OBSIDIAN_VAULT),
        "reminders_file_exists": REMINDERS_FILE.exists(),
        "reminders_file_path": str(REMINDERS_FILE),
    }


@router.get("/reminders")
async def list_reminders(
    user: User = Depends(get_current_user),
):
    """List all Obsidian reminders from Przypomnienia.md."""
    reminders = _parse_reminders()
    return {"reminders": reminders, "total": len(reminders)}


@router.post("/reminders")
async def create_reminder(
    body: ReminderInput,
    user: User = Depends(get_current_user),
):
    """Add a new reminder to Przypomnienia.md."""
    reminders = _parse_reminders()
    new_id = max((r["id"] for r in reminders), default=0) + 1
    reminders.append({
        "id": new_id,
        "text": body.text,
        "done": False,
        "line": len(reminders) + 1,
    })
    _write_reminders(reminders)
    return {"id": new_id, "text": body.text, "done": False}


@router.post("/reminders/{reminder_id}/toggle")
async def toggle_reminder(
    reminder_id: int,
    user: User = Depends(get_current_user),
):
    """Toggle a reminder's done status."""
    reminders = _parse_reminders()
    for r in reminders:
        if r["id"] == reminder_id:
            r["done"] = not r["done"]
            _write_reminders(reminders)
            return {"id": reminder_id, "text": r["text"], "done": r["done"]}
    raise HTTPException(status_code=404, detail="Reminder not found")


@router.delete("/reminders/{reminder_id}")
async def delete_reminder(
    reminder_id: int,
    user: User = Depends(get_current_user),
):
    """Delete a reminder from Przypomnienia.md."""
    reminders = _parse_reminders()
    filtered = [r for r in reminders if r["id"] != reminder_id]
    if len(filtered) == len(reminders):
        raise HTTPException(status_code=404, detail="Reminder not found")
    _write_reminders(filtered)
    return {"deleted": reminder_id}


# ── HTMX partials ──────────────────────────────────────────────────────

_partial_router = APIRouter(prefix="/partials", tags=["obsidian-partials"])


@_partial_router.get("/obsidian-status")
async def partial_obsidian_status(request: Request):
    """HTMX partial for Obsidian vault status."""
    vault_ok = _vault_exists()
    vault_path = str(OBSIDIAN_VAULT)
    reminders_count = len(_parse_reminders())

    return _render_template(request, "partials/obsidian_status.html", {
        "request": request,
        "vault_ok": vault_ok,
        "vault_path": vault_path,
        "reminders_count": reminders_count,
    })


router.include_router(_partial_router)
