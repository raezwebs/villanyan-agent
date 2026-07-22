"""Villanyan-Agent 3.0 — Backend entry point (factory pattern)."""

import os
import pathlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from starlette.templating import Jinja2Templates

load_dotenv()

HERE = pathlib.Path(__file__).parent

# ── Config ────────────────────────────────────────────────────────────
APP_NAME = "Villanyan-Agent 3.0"
APP_VERSION = "3.0.0"
DEBUG = os.getenv("DEBUG", "true").lower() in ("true", "1", "yes")


def create_app() -> FastAPI:
    """Application factory — creates FastAPI instance with all routes."""

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        from backend.core.db import init_db
        await init_db()
        yield

    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        debug=DEBUG,
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────
    _raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
    allowed_origins: list[str] = (
        ["*"] if _raw_origins.strip() == "*"
        else [o.strip() for o in _raw_origins.split(",") if o.strip()]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )

    # ── Jinja2 templates ──────────────────────────────────────────────
    templates_dir = HERE / "templates"
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=True,
        cache_size=50,
    )
    templates = Jinja2Templates(env=env)

    # Make templates available to routes
    app.state.templates = templates

    # ── Static files ──────────────────────────────────────────────────
    static_dir = HERE / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # ── Register routers ──────────────────────────────────────────────
    from backend.routes import auth, system, docker, sessions, hermes, obsidian
    from backend.routes import cloud, github, cron, reminders, network, costs
    from backend.routes import notifications, memory, compat
    from backend.routes import pages  # HTML page routes (frontend)

    routers = [
        auth.router,
        system.router,
        docker.router,
        sessions.router,
        hermes.router,
        obsidian.router,
        cloud.router,
        github.router,
        cron.router,
        reminders.router,
        network.router,
        costs.router,
        notifications.router,
        memory.router,
        compat.router,
        pages.router,
    ]
    for r in routers:
        app.include_router(r)

    # ── Health check ──────────────────────────────────────────────────
    from fastapi import APIRouter
    health = APIRouter()

    @health.get("/api/health")
    async def health_check():
        return {"status": "ok", "app": APP_NAME, "version": APP_VERSION}

    app.include_router(health)

    return app
