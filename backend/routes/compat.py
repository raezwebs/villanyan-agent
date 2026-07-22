"""Villanyan-Agent 3.0 — Legacy compat routes (old frontend API)."""

import os
import pathlib

import psutil
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.db import get_db
from backend.core.models import CronJob, User
from backend.core.security import get_current_user

router = APIRouter(prefix="/api", tags=["compat"])

HERMES_DIR = pathlib.Path(os.path.expanduser("~/.hermes"))


# ── Ports (legacy) ────────────────────────────────────────────────────

@router.get("/ports")
async def legacy_ports(user: User = Depends(get_current_user)):
    """Legacy endpoint — list listening ports."""
    import subprocess
    ports = []
    try:
        result = subprocess.run(
            ["ss", "-tlnp"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("State") or line.startswith("Netid"):
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            local = parts[3]
            if ":" not in local:
                continue
            if "[" in local:
                port_str = local.split("]:")[-1]
            else:
                port_str = local.split(":")[-1]
            try:
                port = int(port_str)
            except ValueError:
                continue
            ports.append({"port": port, "local": local})
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return {"ports": ports, "count": len(ports)}


# ── System resources (legacy) ─────────────────────────────────────────

@router.get("/system/resources")
async def legacy_system_resources(user: User = Depends(get_current_user)):
    """Legacy endpoint — system resources."""
    cpu = psutil.cpu_percent(interval=0.3)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return {
        "cpu_percent": cpu,
        "cpu_count": psutil.cpu_count(),
        "memory_percent": mem.percent,
        "memory_used_gb": round(mem.used / (1024 ** 3), 1),
        "memory_total_gb": round(mem.total / (1024 ** 3), 1),
        "disk_percent": disk.percent,
        "disk_used_gb": round(disk.used / (1024 ** 3), 1),
        "disk_total_gb": round(disk.total / (1024 ** 3), 1),
    }


# ── Hermes memory (legacy) ────────────────────────────────────────────

@router.get("/hermes/memory")
async def legacy_hermes_memory(user: User = Depends(get_current_user)):
    """Legacy endpoint — list memory files (including ~/.hermes/memories/)."""
    if not HERMES_DIR.exists():
        return {"files": [], "total": 0}
    memories_dir = HERMES_DIR / "memories"
    memory_files = []
    for f in sorted(HERMES_DIR.glob("*.md")):
        memory_files.append({
            "name": f.stem,
            "path": str(f),
            "size": f.stat().st_size,
        })
    # Also scan ~/.hermes/memories/*.md
    if memories_dir.exists():
        for f in sorted(memories_dir.glob("*.md")):
            if f.name.endswith(".lock"):
                continue
            memory_files.append({
                "name": "memories/" + f.stem,
                "path": str(f),
                "size": f.stat().st_size,
            })
    return {"files": memory_files, "total": len(memory_files)}


@router.put("/hermes/memory/{name}")
async def legacy_update_memory(
    name: str,
    body: dict,
    user: User = Depends(get_current_user),
):
    """Legacy endpoint — update a memory file."""
    safe_name = pathlib.Path(name).name
    memory_file = HERMES_DIR / f"{safe_name}.md"
    content = body.get("content", "")
    memory_file.write_text(content, encoding="utf-8")
    return {"name": safe_name, "saved": True, "size": len(content)}


# ── Cron (legacy) ─────────────────────────────────────────────────────

@router.get("/cron/list")
async def legacy_cron_list(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Legacy endpoint — list all cron jobs."""
    result = await db.execute(select(CronJob).order_by(CronJob.created_at.desc()))
    jobs = result.scalars().all()
    return {
        "jobs": [
            {
                "id": j.id,
                "name": j.name,
                "schedule": j.schedule,
                "command": j.command,
                "active": j.active,
                "last_run_ts": j.last_run_ts.isoformat() if j.last_run_ts else None,
                "last_exit_code": j.last_exit_code,
            }
            for j in jobs
        ],
        "total": len(jobs),
    }


@router.post("/cron/toggle")
async def legacy_cron_toggle(
    body: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Legacy endpoint — toggle a cron job active state."""
    job_id = body.get("id")
    if not job_id:
        raise HTTPException(status_code=400, detail="Missing job id")
    result = await db.execute(select(CronJob).where(CronJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Cron job not found")
    job.active = not job.active
    await db.flush()
    return {"id": job.id, "active": job.active}
