"""Villanyan-Agent 3.0 — Reminder routes (CRUD)."""

from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.db import get_db
from backend.core.models import Reminder, User
from backend.core.schemas import ReminderCreate, ReminderUpdate
from backend.core.security import get_current_user

router = APIRouter(prefix="/api/reminders", tags=["reminders"])


@router.get("")
async def list_reminders(
    done: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all reminders."""
    query = select(Reminder).order_by(Reminder.priority.desc(), Reminder.created_at.desc())
    if done is not None:
        query = query.where(Reminder.done == done)

    count_q = select(Reminder.id)
    if done is not None:
        count_q = count_q.where(Reminder.done == done)
    total_result = await db.execute(count_q)
    total = len(total_result.scalars().all())

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "items": [
            {
                "id": r.id,
                "text": r.text,
                "done": r.done,
                "priority": r.priority,
                "due_date": r.due_date.isoformat() if r.due_date else None,
                "created_at": r.created_at.isoformat(),
            }
            for r in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("")
async def create_reminder(
    body: ReminderCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new reminder."""
    reminder = Reminder(
        text=body.text,
        priority=body.priority,
        due_date=body.due_date,
    )
    db.add(reminder)
    await db.flush()
    return {
        "id": reminder.id,
        "text": reminder.text,
        "done": reminder.done,
        "priority": reminder.priority,
        "due_date": reminder.due_date.isoformat() if reminder.due_date else None,
        "created_at": reminder.created_at.isoformat(),
    }


@router.get("/{reminder_id}")
async def get_reminder(
    reminder_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a single reminder by ID."""
    result = await db.execute(select(Reminder).where(Reminder.id == reminder_id))
    reminder = result.scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return {
        "id": reminder.id,
        "text": reminder.text,
        "done": reminder.done,
        "priority": reminder.priority,
        "due_date": reminder.due_date.isoformat() if reminder.due_date else None,
        "created_at": reminder.created_at.isoformat(),
    }


@router.patch("/{reminder_id}")
async def update_reminder(
    reminder_id: int,
    body: ReminderUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update a reminder."""
    result = await db.execute(select(Reminder).where(Reminder.id == reminder_id))
    reminder = result.scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(reminder, field, value)
    await db.flush()

    return {
        "id": reminder.id,
        "text": reminder.text,
        "done": reminder.done,
        "priority": reminder.priority,
        "updated": True,
    }


@router.delete("/{reminder_id}")
async def delete_reminder(
    reminder_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a reminder."""
    result = await db.execute(select(Reminder).where(Reminder.id == reminder_id))
    reminder = result.scalar_one_or_none()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    await db.delete(reminder)
    return {"deleted": reminder_id}
