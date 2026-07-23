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
        kwargs = dict(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
        )
        # V4-pro z thinking mode
        if model_name == "deepseek-v4-pro":
            kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
            kwargs["reasoning_effort"] = "high"
        resp = await client.chat.completions.create(**kwargs)
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


# ── check_provider_status (sprawdza dostępność LLM bez duplikacji) ────


async def check_provider_status() -> dict:
    """Sprawdź dostępność wszystkich dostawców LLM.
    Zwraca dict {nazwa: {status, model?, priority}}.
    Używany przez GET /api/hermes/status.
    """
    results = {}

    # DeepSeek
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if api_key and not api_key.startswith("sk-your"):
        try:
            from openai import AsyncOpenAI
            c = AsyncOpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)
            await c.models.list()
            results["deepseek"] = {
                "status": "online",
                "model": os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
                "thinking": True,
                "priority": 1,
            }
        except Exception as e:
            results["deepseek"] = {"status": "error", "error": str(e), "priority": 1}
    else:
        results["deepseek"] = {"status": "no_key", "priority": 1}

    # Ollama
    ollama_url = os.getenv("OLLAMA_API_URL", "http://192.168.1.109:11434")
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(f"{ollama_url}/api/tags")
            models = [m["name"] for m in r.json().get("models", [])] if r.status_code == 200 else []
            if models:
                results["ollama"] = {"status": "online", "models": models, "url": ollama_url, "priority": 2}
            else:
                results["ollama"] = {"status": "offline", "url": ollama_url, "priority": 2}
    except Exception:
        results["ollama"] = {"status": "offline", "url": ollama_url, "priority": 2}

    # Gemini
    gemini_key = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
    results["gemini"] = {"status": "configured" if gemini_key else "no_key", "priority": 3}

    # OpenAI
    openai_key = os.getenv("OPENAI_API_KEY", "")
    results["openai"] = {"status": "configured" if openai_key else "no_key", "priority": 4}

    return results
