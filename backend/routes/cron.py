"""Villanyan-Agent 3.0 — Cron job routes (CRUD + run)."""

from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.db import get_db
from backend.core.models import CronJob, User
from backend.core.schemas import CronJobCreate, CronJobUpdate
from backend.core.security import get_current_user

router = APIRouter(prefix="/api/cron", tags=["cron"])


@router.get("/jobs")
async def list_cron_jobs(
    active: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all cron jobs."""
    query = select(CronJob).order_by(CronJob.created_at.desc())
    if active is not None:
        query = query.where(CronJob.active == active)

    # Total count
    count_q = select(CronJob.id)
    if active is not None:
        count_q = count_q.where(CronJob.active == active)
    total_result = await db.execute(count_q)
    total = len(total_result.scalars().all())

    # Pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    jobs = result.scalars().all()

    return {
        "items": [
            {
                "id": j.id,
                "name": j.name,
                "schedule": j.schedule,
                "command": j.command,
                "active": j.active,
                "last_run_ts": j.last_run_ts.isoformat() if j.last_run_ts else None,
                "last_exit_code": j.last_exit_code,
                "created_at": j.created_at.isoformat(),
            }
            for j in jobs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/jobs")
async def create_cron_job(
    body: CronJobCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new cron job."""
    job = CronJob(
        name=body.name,
        schedule=body.schedule,
        command=body.command,
        active=body.active,
        created_by=user.id,
    )
    db.add(job)
    await db.flush()
    return {
        "id": job.id,
        "name": job.name,
        "schedule": job.schedule,
        "command": job.command,
        "active": job.active,
        "created_at": job.created_at.isoformat(),
    }


@router.get("/jobs/{job_id}")
async def get_cron_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get a single cron job by ID."""
    result = await db.execute(select(CronJob).where(CronJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Cron job not found")
    return {
        "id": job.id,
        "name": job.name,
        "schedule": job.schedule,
        "command": job.command,
        "active": job.active,
        "last_run_ts": job.last_run_ts.isoformat() if job.last_run_ts else None,
        "last_exit_code": job.last_exit_code,
        "created_at": job.created_at.isoformat(),
    }


@router.patch("/jobs/{job_id}")
async def update_cron_job(
    job_id: int,
    body: CronJobUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update a cron job."""
    result = await db.execute(select(CronJob).where(CronJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Cron job not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(job, field, value)
    await db.flush()

    return {
        "id": job.id,
        "name": job.name,
        "schedule": job.schedule,
        "command": job.command,
        "active": job.active,
        "updated": True,
    }


@router.delete("/jobs/{job_id}")
async def delete_cron_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a cron job."""
    result = await db.execute(select(CronJob).where(CronJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Cron job not found")
    await db.delete(job)
    return {"deleted": job_id}


@router.post("/jobs/{job_id}/run")
async def run_cron_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Trigger immediate execution of a cron job."""
    result = await db.execute(select(CronJob).where(CronJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Cron job not found")

    import asyncio
    import subprocess

    now = datetime.now(UTC)
    try:
        proc = await asyncio.create_subprocess_shell(
            job.command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        exit_code = proc.returncode

        job.last_run_ts = now
        job.last_exit_code = exit_code
        await db.flush()

        return {
            "id": job.id,
            "name": job.name,
            "exit_code": exit_code,
            "stdout": stdout.decode("utf-8", errors="replace")[-2000:],
            "stderr": stderr.decode("utf-8", errors="replace")[-2000:],
            "executed_at": now.isoformat(),
        }
    except asyncio.TimeoutError:
        job.last_run_ts = now
        job.last_exit_code = -1
        await db.flush()
        return {
            "id": job.id,
            "name": job.name,
            "exit_code": -1,
            "error": "Command timed out (120s)",
            "executed_at": now.isoformat(),
        }
