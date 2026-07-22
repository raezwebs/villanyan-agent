"""Villanyan-Agent 3.0 — Memory routes (file versioning)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.db import get_db
from backend.core.models import MemoryFileVersion, User
from backend.core.schemas import MemoryFileVersionCreate
from backend.core.security import get_current_user

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("")
async def list_memory_versions(
    file_name: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List memory file versions."""
    query = select(MemoryFileVersion).order_by(MemoryFileVersion.timestamp.desc())

    if file_name:
        query = query.where(MemoryFileVersion.file_name == file_name)

    # Count
    count_q = select(MemoryFileVersion.id)
    if file_name:
        count_q = count_q.where(MemoryFileVersion.file_name == file_name)
    total_result = await db.execute(count_q)
    total = len(total_result.scalars().all())

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    versions = result.scalars().all()

    return {
        "items": [
            {
                "id": v.id,
                "file_name": v.file_name,
                "content": v.content[:200],  # Preview only
                "content_length": len(v.content),
                "has_diff": v.diff is not None,
                "edited_by": v.edited_by,
                "timestamp": v.timestamp.isoformat(),
            }
            for v in versions
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("")
async def create_memory_version(
    body: MemoryFileVersionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new memory file version."""
    version = MemoryFileVersion(
        file_name=body.file_name,
        content=body.content,
        diff=body.diff,
        edited_by=user.id,
    )
    db.add(version)
    await db.flush()
    return {
        "id": version.id,
        "file_name": version.file_name,
        "content_length": len(version.content),
        "has_diff": version.diff is not None,
        "edited_by": version.edited_by,
        "timestamp": version.timestamp.isoformat(),
    }


@router.get("/{version_id}")
async def get_memory_version(
    version_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a full memory version by ID."""
    result = await db.execute(select(MemoryFileVersion).where(MemoryFileVersion.id == version_id))
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="Memory version not found")
    return {
        "id": v.id,
        "file_name": v.file_name,
        "content": v.content,
        "diff": v.diff,
        "edited_by": v.edited_by,
        "timestamp": v.timestamp.isoformat(),
    }


@router.delete("/{version_id}")
async def delete_memory_version(
    version_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a memory version."""
    result = await db.execute(select(MemoryFileVersion).where(MemoryFileVersion.id == version_id))
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(status_code=404, detail="Memory version not found")
    await db.delete(v)
    return {"deleted": version_id}
