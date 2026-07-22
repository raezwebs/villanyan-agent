"""Villanyan-Agent 3.0 — System routes (metrics, service control)."""

import asyncio
import os
import subprocess
import pathlib
from datetime import UTC, datetime

import psutil
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.db import get_db
from backend.core.models import User
from backend.core.security import get_current_user

router = APIRouter(prefix="/api/system", tags=["system"])

PROJECT_DIR = pathlib.Path(__file__).parent.parent.parent


def _format_uptime(seconds: float) -> str:
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    mins = int((seconds % 3600) // 60)
    parts = []
    if days > 0: parts.append(f"{days}d")
    if hours > 0: parts.append(f"{hours}h")
    parts.append(f"{mins}m")
    return " ".join(parts)


def _get_last_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            capture_output=True, text=True, timeout=5,
            cwd=str(PROJECT_DIR),
        )
        if result.returncode == 0:
            return result.stdout.strip()[:60]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "—"


@router.get("/info")
async def get_system_info(user: User = Depends(get_current_user)):
    """System info: version, last commit, uptime."""
    boot_time = psutil.boot_time()
    uptime_seconds = datetime.now(UTC).timestamp() - boot_time
    return {
        "last_commit": _get_last_commit(),
        "uptime": _format_uptime(uptime_seconds),
    }


def _render_template(request: Request, template_name: str, **context):
    """Render Jinja2 template safely (workaround for jinja2 3.1.6 + starlette bug)."""
    env = request.app.state.templates.env
    tmpl = env.get_template(template_name)
    html = tmpl.render({"request": request, **context})
    from starlette.responses import HTMLResponse
    return HTMLResponse(html)


def _get_vcgencmd_temp() -> float | None:
    """Read Pi temperature via vcgencmd."""
    try:
        result = subprocess.run(
            ["vcgencmd", "measure_temp"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0:
            raw = result.stdout.strip()
            # Output: temp=42.5'C
            temp_str = raw.replace("temp=", "").replace("'C", "")
            return round(float(temp_str), 1)
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    return None


def _to_gb(bytes_val: int) -> float:
    return round(bytes_val / (1024 ** 3), 1)


@router.get("/metrics")
async def get_metrics(user: User = Depends(get_current_user)):
    """System resource metrics — CPU, memory, disk, temperature."""
    cpu_percent = psutil.cpu_percent(interval=0.5)
    cpu_count = psutil.cpu_count()

    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    temp = _get_vcgencmd_temp()

    return {
        "cpu_percent": cpu_percent,
        "cpu_count": cpu_count,
        "mem_percent": mem.percent,
        "mem_used": _to_gb(mem.used),
        "mem_total": _to_gb(mem.total),
        "disk_percent": disk.percent,
        "disk_used": _to_gb(disk.used),
        "disk_total": _to_gb(disk.total),
        "temp": temp,
        "updated_at": datetime.now(UTC).isoformat(),
    }


@router.post("/service")
async def control_service(
    body: dict,
    user: User = Depends(get_current_user),
):
    """Start/stop/restart a systemd service."""
    action = body.get("action", "").strip()
    service = body.get("service", "").strip()
    if action not in ("start", "stop", "restart", "status"):
        raise HTTPException(status_code=400, detail="Invalid action (start|stop|restart|status)")
    if not service:
        raise HTTPException(status_code=400, detail="Service name required")

    try:
        result = subprocess.run(
            ["systemctl", action, service],
            capture_output=True, text=True, timeout=15,
        )
        return {
            "service": service,
            "action": action,
            "exit_code": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="systemctl not available")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Command timed out")


# ── HTMX partials ──────────────────────────────────────────────────────

_partial_router = APIRouter(tags=["partials"])


@_partial_router.get("/system-metrics")
async def partial_system_metrics(request: Request):
    """HTMX partial for system metrics cards."""
    cpu_percent = psutil.cpu_percent(interval=0.3)
    cpu_count = psutil.cpu_count()

    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    temp = _get_vcgencmd_temp()

    return _render_template(request, "partials/system_metrics.html",
        cpu_percent=cpu_percent,
        cpu_count=cpu_count,
        mem_percent=mem.percent,
        mem_used=_to_gb(mem.used),
        mem_total=_to_gb(mem.total),
        disk_percent=disk.percent,
        disk_used=_to_gb(disk.used),
        disk_total=_to_gb(disk.total),
        temp=temp,
        updated_at=datetime.now(UTC).strftime("%H:%M:%S"),
    )


# ── Docker list partial ────────────────────────────────────────────────


@_partial_router.get("/docker-list")
async def partial_docker_list(request: Request):
    """HTMX partial for Docker containers list."""
    return _render_template(request, "partials/docker_list.html")


# ── Port table partial ─────────────────────────────────────────────────


@_partial_router.get("/port-table")
async def partial_port_table(request: Request):
    """HTMX partial for port listing."""
    return _render_template(request, "partials/port_table.html")


# ── Cron table partial ─────────────────────────────────────────────────


@_partial_router.get("/cron-table")
async def partial_cron_table(request: Request):
    """HTMX partial for cron jobs table."""
    return _render_template(request, "partials/cron_table.html")


# ── Reminder list partial ──────────────────────────────────────────────


@_partial_router.get("/reminder-list")
async def partial_reminder_list(request: Request):
    """HTMX partial for reminders list."""
    return _render_template(request, "partials/reminder_list.html")


# ── Reminder stats partial ─────────────────────────────────────────────


@_partial_router.get("/reminder-stats")
async def partial_reminder_stats(request: Request):
    """HTMX partial for reminder statistics."""
    return _render_template(request, "partials/reminder_stats.html")


# ── Session list partial ───────────────────────────────────────────────


@_partial_router.get("/session-list")
async def partial_session_list(request: Request):
    """HTMX partial for session list."""
    return _render_template(request, "partials/session_list.html")

