"""Villanyan-Agent 3.0 — Hermes routes (message, agent info, memory files)."""

import os
import pathlib
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.core.llm import generate_response, check_provider_status
from backend.core.models import User
from backend.core.security import get_current_user

router = APIRouter(prefix="/api/hermes", tags=["hermes"])

HERMES_DIR = pathlib.Path(os.path.expanduser("~/.hermes"))


class MessageRequest(BaseModel):
    content: str = Field(..., min_length=1)
    session_id: Optional[str] = None
    model: Optional[str] = None


class MemoryUpdate(BaseModel):
    content: str


# ── Routes ─────────────────────────────────────────────────────────────


@router.post("/message")
async def send_message(
    body: MessageRequest,
    user: User = Depends(get_current_user),
):
    """Send a message to Hermes LLM — DeepSeek → Ollama → Gemini → OpenAI → fallback."""
    prompt = body.content
    model = body.model

    response, used_model = await generate_response(prompt, model)

    return {
        "response": response,
        "model_used": used_model,
        "session_id": body.session_id,
        "user_id": user.id,
    }


@router.get("/status")
async def llm_status(user: User = Depends(get_current_user)):
    """Status wszystkich LLM — który jest dostępny. Deleguje do llm.py."""
    return await check_provider_status()


@router.get("/ollama-status")
async def ollama_status(user: User = Depends(get_current_user)):
    """Check Ollama connection and list available models (legacy compat)."""
    url = os.getenv("OLLAMA_API_URL", "http://192.168.1.109:11434")
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{url}/api/tags")
            if r.status_code == 200:
                models = [m["name"] for m in r.json().get("models", [])]
                return {"online": True, "url": url, "models": models}
    except Exception:
        pass
    return {"online": False, "url": url, "models": []}


@router.get("/agent")
async def get_agent_info(
    user: User = Depends(get_current_user),
):
    """Get Hermes agent configuration and status."""
    config_path = HERMES_DIR / "config.yaml"
    config_content = ""
    if config_path.exists():
        config_content = config_path.read_text(encoding="utf-8")

    return {
        "name": "Hermes Agent",
        "home": str(HERMES_DIR),
        "config_exists": config_path.exists(),
        "config_preview": config_content[:2000] if config_content else "",
        "user": user.username,
    }


@router.get("/memory")
async def list_agent_memory_files(
    user: User = Depends(get_current_user),
):
    """List available memory files in ~/.hermes/ and ~/.hermes/memories/."""
    files = []

    # Scan ~/.hermes/*.md (memory/AGENTS.md, MEMORY.md, SOUL.md, etc.)
    for f in sorted(HERMES_DIR.glob("*.md")):
        files.append({
            "name": f.stem,
            "path": str(f.name),
            "size": f.stat().st_size,
        })

    # Also scan ~/.hermes/memories/*.md
    memories_dir = HERMES_DIR / "memories"
    if memories_dir.exists():
        for f in sorted(memories_dir.glob("*.md")):
            files.append({
                "name": f.stem,
                "path": str(f.relative_to(HERMES_DIR)),
                "size": f.stat().st_size,
            })

    return {"files": files, "total": len(files)}


@router.get("/agent-memory/{name}")
async def get_agent_memory(
    name: str,
    user: User = Depends(get_current_user),
):
    """Read a memory file from ~/.hermes/<name>.md."""
    safe_name = pathlib.Path(name).name
    memory_file = HERMES_DIR / f"{safe_name}.md"

    if not memory_file.exists():
        # Also check in memories/
        alt = HERMES_DIR / "memories" / f"{safe_name}.md"
        if alt.exists():
            memory_file = alt
        else:
            raise HTTPException(status_code=404, detail=f"Memory file {safe_name}.md not found")

    content = memory_file.read_text(encoding="utf-8")
    return {
        "name": safe_name,
        "path": str(memory_file),
        "content": content,
        "size": len(content),
    }


@router.put("/agent-memory/{name}")
async def update_agent_memory(
    name: str,
    body: MemoryUpdate,
    user: User = Depends(get_current_user),
):
    """Write/update a memory file at ~/.hermes/<name>.md."""
    safe_name = pathlib.Path(name).name
    memory_file = HERMES_DIR / f"{safe_name}.md"
    memory_file.parent.mkdir(parents=True, exist_ok=True)
    memory_file.write_text(body.content, encoding="utf-8")

    return {
        "name": safe_name,
        "path": str(memory_file),
        "content": body.content,
        "size": len(body.content),
        "status": "saved",
    }


@router.get("/files")
async def list_all_hermes_files(
    user: User = Depends(get_current_user),
):
    """List ALL files and directories in ~/.hermes/ (recursive, flat).
    Skips .env (secrets) and binary/large files.
    Returns: {files: [{path, name, size, is_dir}], total: N}"""
    items = []
    skip_names = {".env", "state.db", "auth.lock", "chromium-profile",
                   ".cache", "audio_cache", "cache", "backups",
                   "logs", "sessions", "bin", "node_modules", ".git"}

    for f in sorted(HERMES_DIR.iterdir()):
        if f.name.startswith(".") or f.name in skip_names:
            continue
        if f.is_dir():
            # List dir + first-level contents (no deep recursion)
            subitems = []
            for sf in sorted(f.iterdir()):
                if sf.name.startswith("."):
                    continue
                try:
                    subitems.append({
                        "path": str(sf.relative_to(HERMES_DIR)),
                        "name": sf.name,
                        "is_dir": sf.is_dir(),
                        "size": sf.stat().st_size if sf.is_file() else 0,
                    })
                except OSError:
                    pass
            items.append({
                "path": f.name,
                "name": f.name,
                "is_dir": True,
                "size": 0,
                "children": subitems,
                "child_count": len(subitems),
            })
        else:
            try:
                sz = f.stat().st_size
                if sz > 100000:
                    continue
                items.append({"path": f.name, "name": f.name, "is_dir": False, "size": sz})
            except OSError:
                pass

    return {"files": items, "total": len(items)}


@router.get("/files/{path:path}")
async def read_hermes_file(
    path: str,
    user: User = Depends(get_current_user),
):
    """Read any text file from ~/.hermes/ (excluding .env).
    Returns: {path, name, content, size}"""
    safe = pathlib.Path(path)
    if safe.name == ".env":
        raise HTTPException(status_code=403, detail=".env contains secrets — not readable via API")
    target = (HERMES_DIR / path).resolve()
    if not str(target).startswith(str(HERMES_DIR.resolve()) + "/"):
        raise HTTPException(status_code=403, detail="Path traversal")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    try:
        content = target.read_text(encoding="utf-8", errors="replace")
        return {"path": path, "name": target.name, "content": content, "size": len(content)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cannot read file: {e}")
