"""Villanyan-Agent 3.0 — Hermes sessions routes (reads ~/.hermes/state.db)."""

import asyncio
import json
import os
import pathlib
import sqlite3
from datetime import UTC, datetime
from typing import Any, Optional

import httpx

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.core.models import User
from backend.core.security import get_current_user
from backend.core.llm import generate_response


async def _generate_llm_response(prompt: str, model: str | None = None) -> tuple[str, str]:
    """Generuj odpowiedź via LLM chain (DeepSeek → Ollama → Gemini → OpenAI).
    Zwraca (odpowiedź, model_used)."""
    result, used = await generate_response(prompt, model)
    return result, used


class SessionUpdate(BaseModel):
    title: str = ""
    model_config = {"extra": "ignore"}


router = APIRouter(prefix="/api/sessions", tags=["sessions"])
HERMES_STATE_DB = os.path.expanduser("~/.hermes/state.db")
LOCAL_DB = pathlib.Path(__file__).parent.parent.parent / "villanyan-sessions.db"


def _get_or_create_db() -> pathlib.Path:
    """Return path to sessions DB — Hermes state.db if exists, else local fallback."""
    hermes = pathlib.Path(HERMES_STATE_DB)
    if hermes.exists():
        return hermes
    _ensure_local_db(LOCAL_DB)
    return LOCAL_DB


def _ensure_local_db(path: pathlib.Path) -> None:
    """Create minimal sessions schema if it doesn't exist."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT '',
                started_at TEXT NOT NULL,
                source TEXT DEFAULT 'villanyan'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()


def _get_db_path() -> pathlib.Path:
    """Legacy wrapper — raises if state.db missing. Kept for backward compat."""
    p = pathlib.Path(HERMES_STATE_DB)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Hermes state.db not found")
    return p


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def _query_sessions(page: int = 1, page_size: int = 50) -> dict:
    db_path = _get_or_create_db()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        # Get total count
        count_cur = conn.execute("SELECT COUNT(*) as total FROM sessions")
        total = count_cur.fetchone()["total"]

        offset = (page - 1) * page_size
        cur = conn.execute(
            "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ? OFFSET ?",
            (page_size, offset),
        )
        rows = [_row_to_dict(r) for r in cur.fetchall()]
        return {"items": rows, "total": total, "page": page, "page_size": page_size}
    finally:
        conn.close()


def _query_messages(session_id: str, limit: int = 100, before_id: Optional[int] = None) -> list[dict]:
    db_path = _get_or_create_db()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        if before_id:
            cur = conn.execute(
                """SELECT * FROM messages
                   WHERE session_id = ? AND id < ?
                   ORDER BY id DESC LIMIT ?""",
                (session_id, before_id, limit),
            )
        else:
            cur = conn.execute(
                """SELECT * FROM messages
                   WHERE session_id = ?
                   ORDER BY id DESC LIMIT ?""",
                (session_id, limit),
            )
        rows = [_row_to_dict(r) for r in cur.fetchall()]
        # Reverse to chronological order
        rows.reverse()
        return rows
    finally:
        conn.close()


class SessionCreate(BaseModel):
    title: str = ""


@router.get("")
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
):
    """List all Hermes sessions (from ~/.hermes/state.db)."""
    return await asyncio.to_thread(_query_sessions, page, page_size)


@router.post("")
async def create_session(
    body: SessionCreate,
    user: User = Depends(get_current_user),
):
    """Create a new session in Hermes state.db (or local fallback)."""
    db_path = _get_or_create_db()
    conn = sqlite3.connect(str(db_path))
    try:
        now = datetime.now(UTC).isoformat()
        title = body.title or f"Session {now[:19]}"
        try:
            cur = conn.execute(
                "INSERT INTO sessions (title, started_at, source) VALUES (?, ?, 'villanyan')",
                (title, now),
            )
        except sqlite3.OperationalError:
            # Fallback: bez kolumny source (stara schema Hermesa)
            cur = conn.execute(
                "INSERT INTO sessions (title, started_at) VALUES (?, ?)",
                (title, now),
            )
        conn.commit()
        session_id = cur.lastrowid
        return {"id": session_id, "title": title, "started_at": now}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error: {exc}")
    finally:
        conn.close()


@router.get("/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    limit: int = Query(100, ge=1, le=500),
    before_id: Optional[int] = Query(None),
    user: User = Depends(get_current_user),
):
    """Get messages for a session."""
    messages = await asyncio.to_thread(_query_messages, session_id, limit, before_id)
    return {"session_id": session_id, "messages": messages, "count": len(messages)}


@router.patch("/{session_id}")
async def update_session(
    session_id: str,
    body: SessionUpdate,
    user: User = Depends(get_current_user),
):
    """Update a session (title, etc.)."""
    db_path = _get_or_create_db()
    conn = sqlite3.connect(str(db_path))
    try:
        updates = {}
        if body.title:
            updates["title"] = body.title
        if not updates:
            return {"id": session_id, "updated": False}
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [session_id]
        conn.execute(f"UPDATE sessions SET {set_clause} WHERE id = ?", values)
        conn.commit()
        return {"id": session_id, "updated": True, **updates}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error: {exc}")
    finally:
        conn.close()


class MessageSend(BaseModel):
    content: str = Field(..., min_length=1)
    role: str = "user"


@router.post("/{session_id}/send")
async def send_message(
    session_id: str,
    body: MessageSend,
    user: User = Depends(get_current_user),
):
    """Send a message to a session — stores user msg and generates LLM reply."""
    db_path = _get_or_create_db()
    conn = sqlite3.connect(str(db_path))
    try:
        now = datetime.now(UTC).isoformat()
        cur = conn.execute(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, "user", body.content, now),
        )
        conn.execute(
            "UPDATE sessions SET started_at = ? WHERE id = ?",
            (now, session_id),
        )
        conn.commit()
        user_msg_id = cur.lastrowid
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error: {exc}")
    finally:
        conn.close()

    # Generate LLM response (async, outside the first transaction)
    llm_reply, model_used = await _generate_llm_response(body.content)

    # Save assistant reply
    conn2 = sqlite3.connect(str(db_path))
    try:
        now2 = datetime.now(UTC).isoformat()
        cur2 = conn2.execute(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?,?,?,?)",
            (session_id, "assistant", llm_reply, now2),
        )
        conn2.execute(
            "UPDATE sessions SET started_at = ? WHERE id = ?", (now2, session_id)
        )
        conn2.commit()
        return {
            "id": cur2.lastrowid,
            "session_id": session_id,
            "role": "assistant",
            "content": llm_reply,
            "model_used": model_used,
            "timestamp": now2,
            "user_message_id": user_msg_id,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error saving reply: {exc}")
    finally:
        conn2.close()
