"""Villanyan-Agent 3.0 — Hermes routes (message, agent info, memory files)."""

import os
import pathlib
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

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


# ── LLM helpers ────────────────────────────────────────────────────────

async def _try_gemini(prompt: str, model: str | None = None) -> str | None:
    """Try Google Gemini for completion."""
    try:
        from google import genai
        api_key = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
        if not api_key:
            return None
        client = genai.Client(api_key=api_key)
        model_name = model or "gemini-2.0-flash"
        response = client.models.generate_content(model=model_name, contents=prompt)
        return response.text
    except Exception:
        return None


async def _try_openai(prompt: str, model: str | None = None) -> str | None:
    """Try OpenAI for completion."""
    try:
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return None
        client = OpenAI(api_key=api_key)
        model_name = model or "gpt-4o-mini"
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
        )
        return response.choices[0].message.content
    except Exception:
        return None


async def _fallback(prompt: str) -> str:
    """Last-resort fallback — return prompt echo."""
    return f"[Fallback — no LLM configured] Received: {prompt[:100]}..."


# ── Routes ─────────────────────────────────────────────────────────────

@router.post("/message")
async def send_message(
    body: MessageRequest,
    user: User = Depends(get_current_user),
):
    """Send a message to Hermes LLM — tries Gemini → OpenAI → fallback."""
    prompt = body.content
    model = body.model

    response = await _try_gemini(prompt, model) or await _try_openai(prompt, model) or await _fallback(prompt)

    return {
        "response": response,
        "session_id": body.session_id,
        "user_id": user.id,
    }


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


@router.get("/agent-memory/{name}")
async def get_agent_memory(
    name: str,
    user: User = Depends(get_current_user),
):
    """Read a memory file from ~/.hermes/<name>.md."""
    # Prevent path traversal
    safe_name = pathlib.Path(name).name
    memory_file = HERMES_DIR / f"{safe_name}.md"

    if not memory_file.exists():
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
