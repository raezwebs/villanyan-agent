"""Villanyan-Agent 3.0 — Cloud file routes (~/cloudilla)."""

import os
import pathlib
import shutil
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from backend.core.models import User
from backend.core.security import get_current_user

router = APIRouter(prefix="/api/cloud", tags=["cloud"])

CLOUD_ROOT = pathlib.Path(os.path.expanduser("~/cloudilla"))


def _resolve_path(relative: str) -> pathlib.Path:
    """Resolve a path safely — prevents traversal outside CLOUD_ROOT.
    
    If CLOUD_ROOT or the target path does not exist, returns the path
    without resolving (avoids 403 on missing directory).
    """
    clean = relative.lstrip("/")
    resolved = (CLOUD_ROOT / clean).resolve()
    # If resolved IS CLOUD_ROOT itself (empty path), it's always safe
    if resolved == CLOUD_ROOT.resolve():
        return resolved
    # If it doesn't exist, resolve() may produce an unexpected path;
    # normalize manually instead
    if not resolved.exists() or not CLOUD_ROOT.exists():
        manual = (CLOUD_ROOT / clean)
        # Still check traversal
        try:
            manual_resolved = manual.resolve(strict=False)
            root_resolved = CLOUD_ROOT.resolve(strict=False)
            if str(manual_resolved) != str(root_resolved) and not str(manual_resolved).startswith(str(root_resolved) + '/'):
                raise HTTPException(status_code=403, detail="Path traversal detected")
        except (ValueError, OSError):
            pass
        return manual
    if not str(resolved).startswith(str(CLOUD_ROOT.resolve()) + '/'):
        raise HTTPException(status_code=403, detail="Path traversal detected")
    return resolved


def _stat_to_dict(p: pathlib.Path) -> dict:
    st = p.stat()
    return {
        "name": p.name,
        "path": str(p.relative_to(CLOUD_ROOT)),
        "is_dir": p.is_dir(),
        "size": st.st_size,
        "modified": st.st_mtime,
        "created": st.st_ctime,
    }


class MkdirInput(BaseModel):
    path: str = Field(..., min_length=1)


class UploadResponse(BaseModel):
    name: str
    path: str
    size: int


@router.get("/files")
async def list_files(
    path: str = "",
    user: User = Depends(get_current_user),
):
    """List files in cloud directory."""
    if not CLOUD_ROOT.exists():
        return {"path": path or "/", "entries": [], "total": 0,
                "note": "Cloudilla nie skonfigurowana — ustaw CLOUD_ROOT w .env"}
    
    target = _resolve_path(path)

    if not target.exists():
        return {"path": path or "/", "entries": [], "total": 0, "note": "Path not found"}
    if not target.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    return {
        "path": path or "/",
        "entries": [_stat_to_dict(e) for e in entries],
        "total": len(entries),
    }


@router.post("/upload")
async def upload_file(
    file: UploadFile,
    path: str = "",
    user: User = Depends(get_current_user),
):
    """Upload a file to cloud directory."""
    target_dir = _resolve_path(path)
    if not target_dir.exists():
        raise HTTPException(status_code=404, detail="Directory not found")
    if not target_dir.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    dest = target_dir / (file.filename or "uploaded_file")
    content = await file.read()
    dest.write_bytes(content)

    return {
        "name": dest.name,
        "path": str(dest.relative_to(CLOUD_ROOT)),
        "size": len(content),
    }


@router.post("/mkdir")
async def make_directory(
    body: MkdirInput,
    user: User = Depends(get_current_user),
):
    """Create a directory in the cloud."""
    target = _resolve_path(body.path)

    if target.exists():
        raise HTTPException(status_code=400, detail="Path already exists")

    target.mkdir(parents=True, exist_ok=True)
    return {
        "path": str(target.relative_to(CLOUD_ROOT)),
        "created": True,
    }


@router.delete("/files/{path:path}")
async def delete_file(
    path: str,
    user: User = Depends(get_current_user),
):
    """Delete a file or directory from the cloud."""
    target = _resolve_path(path)

    if not target.exists():
        raise HTTPException(status_code=404, detail="Path not found")

    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()

    return {"deleted": str(target.relative_to(CLOUD_ROOT))}
