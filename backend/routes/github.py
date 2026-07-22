"""Villanyan-Agent 3.0 — GitHub routes (projects via gh CLI)."""

import json
import subprocess

from fastapi import APIRouter, Depends, HTTPException

from backend.core.models import User
from backend.core.security import get_current_user

router = APIRouter(prefix="/api/github", tags=["github"])


@router.get("/projects")
async def list_projects(user: User = Depends(get_current_user)):
    """List GitHub repos for raezwebs via gh CLI."""
    try:
        result = subprocess.run(
            ["gh", "repo", "list", "raezwebs", "--json", "name,description,pushedAt"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise HTTPException(
                status_code=502,
                detail=f"gh CLI error: {result.stderr.strip()}",
            )
        repos = json.loads(result.stdout)
        return {
            "owner": "raezwebs",
            "repos": repos,
            "total": len(repos),
        }
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="gh CLI not installed")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to parse gh output: {exc}")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="gh command timed out")
