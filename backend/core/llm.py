"""backend/core/llm.py — wspólna logika LLM dla całego projektu.

Hierarchia fallback:
  1. DeepSeek API   — primary (deepseek-v4-flash / deepseek-v4-pro)
  2. Ollama         — lokalny RPi
  3. Gemini         — Google cloud
  4. OpenAI         — OpenAI cloud
  5. Echo fallback  — gdy wszystko zawiedzie

Docs: https://api-docs.deepseek.com/
"""
from __future__ import annotations
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
VALID_DEEPSEEK_MODELS = {"deepseek-v4-flash", "deepseek-v4-pro"}

# ── try_deepseek ──────────────────────────────────────────────────────


async def try_deepseek(prompt: str, model: Optional[str] = None) -> Optional[str]:
    """Primary LLM — DeepSeek API (OpenAI-compatible).

    Requires DEEPSEEK_API_KEY in .env.
    Both v4-flash and v4-pro support thinking mode.
    """
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key or api_key.startswith("sk-your"):
        return None

    from openai import AsyncOpenAI

    model_name = (
        model if model in VALID_DEEPSEEK_MODELS
        else os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    )
    try:
        client = AsyncOpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)
        resp = await client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}},
        )
        text = resp.choices[0].message.content
        return text.strip() if text else None
    except Exception as e:
        logger.warning("DeepSeek API error: %s", e)
        return None


# ── try_ollama ────────────────────────────────────────────────────────


async def try_ollama(prompt: str, model: Optional[str] = None) -> Optional[str]:
    """Local Ollama fallback."""
    url = os.getenv("OLLAMA_API_URL", "http://192.168.1.109:11434")
    m = model or os.getenv("OLLAMA_MODEL", "deepseek-r1:1.5b")
    try:
        async with httpx.AsyncClient(timeout=90.0) as c:
            r = await c.post(
                f"{url}/api/generate",
                json={"model": m, "prompt": prompt, "stream": False},
            )
            if r.status_code == 200:
                text = r.json().get("response", "").strip()
                return text or None
    except Exception:
        return None


# ── try_gemini ────────────────────────────────────────────────────────


async def try_gemini(prompt: str, model: Optional[str] = None) -> Optional[str]:
    """Google Gemini fallback."""
    try:
        from google import genai

        key = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
        if not key:
            return None
        client = genai.Client(api_key=key)
        r = client.models.generate_content(
            model=model or "gemini-2.0-flash", contents=prompt
        )
        return r.text
    except Exception:
        return None


# ── try_openai ────────────────────────────────────────────────────────


async def try_openai(prompt: str, model: Optional[str] = None) -> Optional[str]:
    """OpenAI fallback."""
    try:
        from openai import OpenAI

        key = os.getenv("OPENAI_API_KEY", "")
        if not key:
            return None
        client = OpenAI(api_key=key)
        r = client.chat.completions.create(
            model=model or "gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
        )
        return r.choices[0].message.content
    except Exception:
        return None


# ── generate_response (główna funkcja) ────────────────────────────────


async def generate_response(
    prompt: str,
    model: Optional[str] = None,
) -> tuple[str, str]:
    """Generuj odpowiedź LLM.

    Zwraca (odpowiedź, nazwa_modelu_który_odpowiedział).
    Kolejność: DeepSeek → Ollama → Gemini → OpenAI → fallback.
    """
    result = await try_deepseek(prompt, model)
    if result:
        m = (
            model if model in VALID_DEEPSEEK_MODELS
            else os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
        )
        return result, f"deepseek/{m}"

    result = await try_ollama(prompt, model)
    if result:
        return result, f"ollama/{os.getenv('OLLAMA_MODEL', 'local')}"

    result = await try_gemini(prompt, model)
    if result:
        return result, "gemini/2.0-flash"

    result = await try_openai(prompt, model)
    if result:
        return result, "openai/gpt-4o-mini"

    return (
        f"[Brak LLM] Sprawdź DEEPSEEK_API_KEY w .env "
        f"lub połączenie z Ollama ({os.getenv('OLLAMA_API_URL')})",
        "fallback",
    )
