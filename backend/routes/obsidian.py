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

_partial_router = APIRouter(tags=["obsidian-partials"])


@_partial_router.get("/obsidian-status")
async def partial_obsidian_status(request: Request):
    """HTMX partial for Obsidian vault status."""
    vault_ok = _vault_exists()
    vault_path = str(OBSIDIAN_VAULT)
    reminders_count = len(_parse_reminders())

    return _render_template(
        request, "partials/obsidian_status.html",
        vault_ok=vault_ok,
        vault_path=vault_path,
        reminders_count=reminders_count,
    )


# Register _partial_router in main.py under /partials prefix
# (not here — router.include_router is disabled to avoid double-registration)
# router.include_router(_partial_router)


# ── Vault browsing ─────────────────────────────────────────────────────


@router.get("/notes")
async def list_notes(
    path: str = "",
    user: User = Depends(get_current_user),
):
    """List notes and folders in Obsidian vault."""
    if not _vault_exists():
        return {"notes": [], "folders": [], "vault_exists": False}
    target = (OBSIDIAN_VAULT / path.lstrip("/")).resolve()
    if not str(target).startswith(str(OBSIDIAN_VAULT.resolve()) + '/'):
        raise HTTPException(status_code=403, detail="Path traversal")
    notes, folders = [], []
    for item in sorted(target.iterdir()):
        if item.name.startswith("."):
            continue
        if item.is_dir():
            folders.append({"name": item.name, "path": str(item.relative_to(OBSIDIAN_VAULT))})
        elif item.suffix == ".md":
            notes.append({
                "name": item.stem,
                "path": str(item.relative_to(OBSIDIAN_VAULT)),
                "size": item.stat().st_size,
                "modified": datetime.fromtimestamp(item.stat().st_mtime, UTC).isoformat(),
            })
    return {"notes": notes, "folders": folders, "vault_exists": True, "current_path": path}


@router.get("/notes/read")
async def read_note(
    path: str,
    user: User = Depends(get_current_user),
):
    """Read a specific note from Obsidian vault."""
    target = (OBSIDIAN_VAULT / path.lstrip("/")).resolve()
    if not str(target).startswith(str(OBSIDIAN_VAULT.resolve()) + '/'):
        raise HTTPException(status_code=403, detail="Path traversal")
    if not target.exists():
        raise HTTPException(status_code=404, detail="Note not found")
    return {
        "path": path,
        "name": target.stem,
        "content": target.read_text(encoding="utf-8"),
        "size": target.stat().st_size,
    }


@router.put("/notes/write")
async def write_note(
    body: dict,
    user: User = Depends(get_current_user),
):
    """Write/update a note in Obsidian vault."""
    path = body.get("path", "").lstrip("/")
    content = body.get("content", "")
    target = (OBSIDIAN_VAULT / path).resolve()
    if not str(target).startswith(str(OBSIDIAN_VAULT.resolve()) + '/'):
        raise HTTPException(status_code=403, detail="Path traversal")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"path": path, "saved": True, "size": len(content)}
