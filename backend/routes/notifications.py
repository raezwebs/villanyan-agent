"""Villanyan-Agent 3.0 — Notifications routes (SSE streaming)."""

import asyncio
import json
import time
from collections import deque
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from backend.core.models import User
from backend.core.security import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

# ── In-memory event bus ────────────────────────────────────────────────
# A simple deque holds pending notification events.
# Collectors (background tasks) push events here.
# SSE clients consume from here.

_event_queue: deque[dict[str, Any]] = deque(maxlen=500)
_event_id_counter: int = 0


def push_notification(event_type: str, data: Any) -> dict:
    """Push an event to the notification bus. Used by collectors."""
    global _event_id_counter
    _event_id_counter += 1
    event = {
        "id": _event_id_counter,
        "type": event_type,
        "data": data,
        "timestamp": time.time(),
    }
    _event_queue.append(event)
    return event


# ── Routes ─────────────────────────────────────────────────────────────

@router.get("")
async def list_notifications(
    limit: int = 50,
    event_type: Optional[str] = None,
    user: User = Depends(get_current_user),
):
    """Get recent notifications."""
    items = list(_event_queue)
    if event_type:
        items = [e for e in items if e["type"] == event_type]
    items = items[-limit:]
    items.reverse()  # newest first
    return {"items": items, "total": len(items)}


@router.post("/read")
async def mark_read(
    body: dict,
    user: User = Depends(get_current_user),
):
    """Mark notifications as read (clears from queue)."""
    notification_id = body.get("id")
    if notification_id:
        # Remove single notification
        to_remove = [e for e in _event_queue if e["id"] == notification_id]
        for e in to_remove:
            _event_queue.remove(e)
        return {"cleared": 1, "remaining": len(_event_queue)}
    else:
        # Clear all
        count = len(_event_queue)
        _event_queue.clear()
        return {"cleared": count, "remaining": 0}


# ── SSE streaming ──────────────────────────────────────────────────────

@router.get("/stream")
async def event_stream(request: Request):
    """SSE endpoint — streams notifications to connected clients."""
    from sse_starlette.sse import EventSourceResponse

    last_id = 0

    async def event_generator():
        nonlocal last_id
        # Seed with existing events
        for event in list(_event_queue):
            if event["id"] > last_id:
                last_id = event["id"]
                yield {
                    "event": event["type"],
                    "id": str(event["id"]),
                    "data": json.dumps(event["data"]),
                }

        # Poll for new events
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            current_queue = list(_event_queue)
            for event in current_queue:
                if event["id"] > last_id:
                    last_id = event["id"]
                    yield {
                        "event": event["type"],
                        "id": str(event["id"]),
                        "data": json.dumps(event["data"]),
                    }

            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())
