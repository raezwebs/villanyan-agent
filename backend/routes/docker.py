"""Villanyan-Agent 3.0 — Docker routes."""

from fastapi import APIRouter, Depends, HTTPException, status

from backend.core.models import User
from backend.core.security import get_current_user

router = APIRouter(prefix="/api/docker", tags=["docker"])


def _get_docker_client():
    """Get Docker client, raising 503 if unavailable."""
    try:
        import docker
        client = docker.from_env()
        client.ping()
        return client
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Docker not available: {exc}",
        )


@router.get("/containers")
async def list_containers(user: User = Depends(get_current_user)):
    """List all Docker containers (running + stopped)."""
    client = _get_docker_client()
    try:
        containers = client.containers.list(all=True)
        result = []
        for c in containers:
            ports_info = {}
            if c.ports:
                for container_port, mappings in c.ports.items():
                    if mappings:
                        ports_info[str(container_port)] = [
                            {"host_ip": m.get("HostIp", ""), "host_port": m.get("HostPort", "")}
                            for m in mappings
                        ]
            result.append({
                "id": c.id[:12],
                "name": c.name,
                "image": c.image.tags[0] if c.image.tags else c.image.short_id,
                "status": c.status,
                "state": c.status,
                "ports": ports_info,
                "created": c.attrs.get("Created", ""),
            })
        return {"containers": result, "total": len(result)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error listing containers: {exc}")
    finally:
        client.close()


@router.post("/containers/{container_id}/{action}")
async def control_container(
    container_id: str,
    action: str,
    user: User = Depends(get_current_user),
):
    """Start/stop/restart/pause/unpause a container."""
    if action not in ("start", "stop", "restart", "pause", "unpause", "kill"):
        raise HTTPException(status_code=400, detail=f"Invalid action: {action}")

    client = _get_docker_client()
    try:
        container = client.containers.get(container_id)
        getattr(container, action)()
        container.reload()
        return {
            "id": container.id[:12],
            "name": container.name,
            "action": action,
            "status": container.status,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error: {exc}")
    finally:
        client.close()
