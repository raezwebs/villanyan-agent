"""Villanyan-Agent 3.0 — System routes (metrics, service control)."""

import asyncio
import json
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


# ── Dashboard summary ──────────────────────────────────────────────────


@_partial_router.get("/dashboard-summary")
async def partial_dashboard_summary(request: Request):
    """HTMX partial: dashboard summary — docker, system, obsidian."""
    import json
    docker_html = ""
    try:
        import docker
        client = docker.from_env()
        containers = client.containers.list(all=True)[:5]
        for c in containers:
            status_class = "bg-success" if c.status == "running" else "bg-secondary"
            image_name = c.image.tags[0].split(":")[0] if c.image.tags else c.image.short_id[:12]
            docker_html += (
                f'<div class="flex items-center gap-2 py-1.5 border-b border-border-custom/50 last:border-0">'
                f'<span class="w-2 h-2 rounded-full shrink-0 {status_class}"></span>'
                f'<span class="text-sm font-medium truncate flex-1">{c.name}</span>'
                f'<span class="text-[10px] text-secondary/60">{image_name}</span>'
                f"</div>"
            )
        client.close()
    except Exception:
        docker_html = '<div class="text-xs text-secondary/60 py-2 text-center">Docker offline</div>'

    if not docker_html:
        docker_html = '<div class="text-xs text-secondary py-2 text-center">Brak kontenerów</div>'

    # System info
    import subprocess
    commit = ""
    try:
        r = subprocess.run(["git", "log", "--oneline", "-1"], capture_output=True, text=True, timeout=5,
                          cwd=str(PROJECT_DIR))
        commit = r.stdout.strip()[:50] if r.returncode == 0 else ""
    except: pass

    import psutil
    boot_time = psutil.boot_time()
    uptime_seconds = datetime.now(UTC).timestamp() - boot_time
    days = int(uptime_seconds // 86400)
    hours = int((uptime_seconds % 86400) // 3600)
    uptime_str = f"{days}d {hours}h" if days else f"{hours}h"

    temp = _get_vcgencmd_temp() or "—"

    # Obsidian
    obsidian_ok = "✓" if pathlib.Path(os.path.expanduser("~/obsidian-vault/Hermes/Przypomnienia.md")).exists() else "✗"
    obsidian_path = "/home/vv-rp/obsidian-vault"

    # Cloudilla
    cloud_root = pathlib.Path(os.path.expanduser("~/cloudilla"))
    cloud_count = len(list(cloud_root.iterdir())) if cloud_root.exists() else 0

    return _render_template(request, "partials/dashboard_summary.html",
        docker_html=docker_html,
        uptime=uptime_str,
        temp=temp,
        commit=commit,
        obsidian_ok=obsidian_ok,
        obsidian_path=obsidian_path,
        cloud_count=cloud_count,
    )


@_partial_router.get("/docker-list")
async def partial_docker_list(request: Request):
    """HTMX partial for Docker containers list — server-rendered."""
    import docker
    try:
        client = docker.from_env()
        containers = client.containers.list(all=True)
        client.close()
        return _render_template(request, "partials/docker_list.html",
            containers=containers,
            docker_error=None,
            total=len(containers),
        )
    except Exception as e:
        return _render_template(request, "partials/docker_list.html",
            containers=[],
            docker_error=str(e),
            total=0,
        )


# ── Port table partial ─────────────────────────────────────────────────


@_partial_router.get("/port-table")
async def partial_port_table(request: Request):
    """HTMX partial for port listing — server-rendered."""
    import subprocess
    ports = []
    try:
        result = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line or line.startswith("State") or line.startswith("Netid"):
                    continue
                parts = line.split()
                if len(parts) < 4: continue
                local = parts[3]
                if ":" not in local: continue
                port_str = local.split("]:")[-1] if "[" in local else local.split(":")[-1]
                try:
                    port = int(port_str)
                except ValueError:
                    continue
                process_info = parts[4] if len(parts) >= 5 else ""
                ports.append({"port": port, "local": local, "process": process_info})
        ports.sort(key=lambda p: p["port"])
    except Exception:
        ports = []

    KNOWN_PORTS = {
        22: "SSH", 80: "HTTP", 443: "HTTPS", 445: "SMB",
        7890: "villanyan", 8642: "hermes-gateway",
        11434: "ollama", 27124: "obsidian-mcp",
        6080: "novnc", 5900: "VNC",
        8080: "nextcloud", 8081: "static-site",
        9000: "portainer",
    }
    return _render_template(request, "partials/port_table.html",
        ports=ports,
        known_ports=KNOWN_PORTS,
    )


# ── Obsidian status partial ─────────────────────────────────────────────


@_partial_router.get("/obsidian-status")
async def partial_obsidian_status(request: Request):
    """HTMX partial for Obsidian vault status — server-rendered."""
    vault_path = pathlib.Path(os.path.expanduser("~/obsidian-vault"))
    vault_ok = vault_path.exists()
    reminders_ok = (vault_path / "Hermes" / "Przypomnienia.md").exists()
    note_count = 0
    if vault_ok:
        note_count = len(list(vault_path.rglob("*.md")))
    return _render_template(request, "partials/obsidian_status.html",
        vault_ok=vault_ok,
        vault_path=str(vault_path),
        reminders_ok=reminders_ok,
        note_count=note_count,
    )


# ── Cloud files partial ────────────────────────────────────────────────


@_partial_router.get("/cloud-files")
async def partial_cloud_files(request: Request):
    """HTMX partial: list cloudilla files — server-rendered."""
    cloud_root = pathlib.Path(os.path.expanduser("~/cloudilla"))
    entries = []
    if cloud_root.exists():
        for item in sorted(cloud_root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            st = item.stat()
            entries.append({
                "name": item.name,
                "is_dir": item.is_dir(),
                "size": st.st_size,
                "modified": int(st.st_mtime),
            })
    return _render_template(request, "partials/cloud_files.html", entries=entries)


# ── GitHub projects partial ────────────────────────────────────────────


@_partial_router.get("/github-projects")
async def partial_github_projects(request: Request):
    """HTMX partial: list GitHub repos — server-rendered."""
    repos = []
    error = None
    try:
        result = subprocess.run(
            ["gh", "repo", "list", "raezwebs", "--json", "name,description,pushedAt", "--limit", "15"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            repos = json.loads(result.stdout) if result.stdout.strip() else []
        else:
            error = result.stderr.strip()
    except FileNotFoundError:
        error = "gh CLI not installed"
    except json.JSONDecodeError:
        error = "Failed to parse gh output"
    except subprocess.TimeoutExpired:
        error = "gh timed out"
    except Exception as e:
        error = str(e)
    return _render_template(request, "partials/github_projects.html", repos=repos, error=error)


# ── System summary partial ─────────────────────────────────────────────


@_partial_router.get("/system-summary")
async def partial_system_summary(request: Request):
    """HTMX partial: system info summary — server-rendered."""
    import psutil
    boot_time = psutil.boot_time()
    uptime_seconds = datetime.now(UTC).timestamp() - boot_time
    days = int(uptime_seconds // 86400)
    hours = int((uptime_seconds % 86400) // 3600)
    uptime_str = f"{days}d {hours}h" if days else f"{hours}h"
    temp = _get_vcgencmd_temp() or "—"
    temp_display = f"{temp}°C" if isinstance(temp, float) else temp

    # Obsidian
    obsidian_path = pathlib.Path(os.path.expanduser("~/obsidian-vault"))
    obsidian_ok = obsidian_path.exists()

    return _render_template(request, "partials/system_summary.html",
        uptime=uptime_str,
        temp=temp_display,
        obsidian_ok=obsidian_ok,
    )


# ── Dashboard welcome partial ──────────────────────────────────────────


@_partial_router.get("/dashboard-welcome")
async def partial_dashboard_welcome(request: Request):
    """HTMX partial: welcome + reminder counts from Obsidian vault."""
    pending = 0
    done = 0
    reminders_file = pathlib.Path(os.path.expanduser("~/obsidian-vault/Hermes/Przypomnienia.md"))
    if reminders_file.exists():
        for line in reminders_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("- [x]"):
                done += 1
            elif line.startswith("- [ ]") or line.startswith("- "):
                pending += 1

    return _render_template(request, "partials/dashboard_welcome.html",
        pending=pending,
        done=done,
        total=pending + done,
    )


@_partial_router.get("/cron-table")
async def partial_cron_table(request: Request):
    """HTMX partial: cron jobs from Hermes ~/.hermes/cron/jobs.json."""
    jobs = []
    cron_file = pathlib.Path(os.path.expanduser("~/.hermes/cron/jobs.json"))
    if cron_file.exists():
        try:
            import json as _json
            data = _json.loads(cron_file.read_text(encoding="utf-8"))
            raw_jobs = data.get("jobs", data) if isinstance(data, dict) else data
            if isinstance(raw_jobs, list):
                for j in raw_jobs:
                    schedule = j.get("schedule", {})
                    if isinstance(schedule, dict):
                        expr = schedule.get("expr", schedule.get("display", "—"))
                    else:
                        expr = str(schedule)
                    jobs.append({
                        "name": j.get("name", "?"),
                        "id": j.get("id", ""),
                        "schedule": {"display": expr},
                        "active": True,
                    })
        except Exception:
            pass

    return _render_template(request, "partials/cron_table.html", jobs=jobs)


@_partial_router.get("/cron-table-villanyan")
async def partial_cron_table_villanyan(request: Request):
    """HTMX partial: cron jobs from villanyan-agent DB."""
    from backend.core.db import async_session_factory
    from backend.core.models import CronJob
    from sqlalchemy import select

    db_jobs = []
    try:
        async with async_session_factory() as session:
            result = await session.execute(select(CronJob).order_by(CronJob.created_at.desc()))
            for j in result.scalars().all():
                db_jobs.append({
                    "name": j.name,
                    "id": j.id,
                    "schedule": {"display": j.schedule},
                    "command": j.command,
                    "active": j.active,
                    "last_run_ts": j.last_run_ts,
                    "last_exit_code": j.last_exit_code,
                })
    except Exception:
        pass

    return _render_template(request, "partials/cron_table_villanyan.html", jobs=db_jobs)


# ── Reminder list partial (serwer-render) ──────────────────────────────


@_partial_router.get("/reminder-list")
async def partial_reminder_list(request: Request):
    """HTMX partial: reminders from Obsidian vault Hermes/Przypomnienia.md."""
    reminders = []
    reminders_file = pathlib.Path(os.path.expanduser("~/obsidian-vault/Hermes/Przypomnienia.md"))
    if reminders_file.exists():
        for line in reminders_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("- [ ]"):
                text = line[5:].strip()
                important = "**[VERIFY]" in text or "**[WAŻNE]" in text
                # Extract tag if in **bold**
                tag = ""
                if "**" in text:
                    parts = text.split("**")
                    if len(parts) >= 3:
                        tag = parts[1].strip("[]")
                reminders.append({"id": len(reminders) + 1, "text": text, "done": False, "important": important, "tag": tag})
            elif line.startswith("- [x]"):
                text = line[5:].strip()
                reminders.append({"id": len(reminders) + 1, "text": text, "done": True, "important": False, "tag": ""})
            elif line.startswith("- "):
                reminders.append({"id": len(reminders) + 1, "text": line[2:].strip(), "done": False, "important": False, "tag": ""})

    return _render_template(request, "partials/reminder_list.html", reminders=reminders)


# ── Reminder stats partial (serwer-render) ─────────────────────────────


@_partial_router.get("/reminder-stats")
async def partial_reminder_stats(request: Request):
    """HTMX partial: reminder statistics from Obsidian vault."""
    total = 0
    done_count = 0
    reminders_file = pathlib.Path(os.path.expanduser("~/obsidian-vault/Hermes/Przypomnienia.md"))
    if reminders_file.exists():
        for line in reminders_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("- [ ]") or line.startswith("- "):
                total += 1
            elif line.startswith("- [x]"):
                total += 1
                done_count += 1

    return _render_template(request, "partials/reminder_stats.html",
        total=total, pending=total - done_count, done=done_count)


# ── Session list partial ───────────────────────────────────────────────


@_partial_router.get("/session-list")
async def partial_session_list(request: Request):
    """HTMX partial for session list."""
    return _render_template(request, "partials/session_list.html")


# ── Persona brain partials ─────────────────────────────────────────────


@_partial_router.get("/persona-files")
async def partial_persona_files(request: Request):
    """HTMX partial: list memory files + agent info."""
    HERMES_DIR = pathlib.Path(os.path.expanduser("~/.hermes"))
    files = []

    # Root .md files
    for f in sorted(HERMES_DIR.glob("*.md")):
        files.append({"name": f.stem, "path": str(f.name), "size": f.stat().st_size, "subfolder": False})

    # memories/ subfolder
    memories_dir = HERMES_DIR / "memories"
    if memories_dir.exists():
        for f in sorted(memories_dir.glob("*.md")):
            files.append({"name": f.stem, "path": str(f.relative_to(HERMES_DIR)), "size": f.stat().st_size, "subfolder": True})

    # Deduplicate
    seen = set()
    unique_files = []
    for f in files:
        if f["name"] not in seen:
            seen.add(f["name"])
            unique_files.append(f)

    # Agent info
    config_path = HERMES_DIR / "config.yaml"
    agent_info = {
        "name": "Hermes Agent",
        "home": str(HERMES_DIR),
        "config_exists": config_path.exists(),
    }

    # Active file from query param
    active_file = request.query_params.get("file", "")

    file_content = ""
    file_name = ""
    file_size = 0
    file_saved = request.query_params.get("saved", "") == "true"

    if active_file:
        safe_name = pathlib.Path(active_file).name
        fpath = HERMES_DIR / f"{safe_name}.md"
        if not fpath.exists():
            fpath = HERMES_DIR / "memories" / f"{safe_name}.md"
        if fpath.exists():
            file_content = fpath.read_text(encoding="utf-8")
            file_name = safe_name
            file_size = fpath.stat().st_size

    return _render_template(request, "partials/persona_brain.html",
        files=unique_files,
        agent_info=agent_info,
        active_file=active_file,
        file_content=file_content,
        file_name=file_name,
        file_size=file_size,
        file_saved=file_saved,
    )


@_partial_router.post("/persona-file/{name}/save")
async def partial_persona_save(request: Request, name: str):
    """HTMX POST: save memory file content."""
    HERMES_DIR = pathlib.Path(os.path.expanduser("~/.hermes"))
    form = await request.form()
    content = form.get("content", "")
    safe_name = pathlib.Path(name).name
    memory_file = HERMES_DIR / f"{safe_name}.md"
    memory_file.parent.mkdir(parents=True, exist_ok=True)
    memory_file.write_text(content, encoding="utf-8")

    # Refresh partial with saved flag
    files = []
    for f in sorted(HERMES_DIR.glob("*.md")):
        files.append({"name": f.stem, "path": str(f.name), "size": f.stat().st_size, "subfolder": False})
    memories_dir = HERMES_DIR / "memories"
    if memories_dir.exists():
        for f in sorted(memories_dir.glob("*.md")):
            files.append({"name": f.stem, "path": str(f.relative_to(HERMES_DIR)), "size": f.stat().st_size, "subfolder": True})
    seen = set()
    unique_files = []
    for f in files:
        if f["name"] not in seen: seen.add(f["name"]); unique_files.append(f)

    config_path = HERMES_DIR / "config.yaml"
    agent_info = {
        "name": "Hermes Agent",
        "home": str(HERMES_DIR),
        "config_exists": config_path.exists(),
    }

    return _render_template(request, "partials/persona_brain.html",
        files=unique_files,
        agent_info=agent_info,
        active_file=safe_name,
        file_content=content,
        file_name=safe_name,
        file_size=len(content),
        file_saved=True,
    )

