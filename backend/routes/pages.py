"""Villanyan-Agent 3.0 — Page routes (frontend HTML)."""

from fastapi import APIRouter, Request
from starlette.templating import _TemplateResponse

router = APIRouter(tags=["pages"])


def _render(request: Request, template: str, **context):
    """Render Jinja2 template by hand (workaround for starlette + jinja2 bug)."""
    env = request.app.state.templates.env
    tmpl = env.get_template(template)
    html = tmpl.render({"request": request, **context})
    from starlette.responses import HTMLResponse
    return HTMLResponse(html)


@router.get("/", include_in_schema=False)
async def index(request: Request):
    return _render(request, "dashboard.html")


@router.get("/login", include_in_schema=False)
async def login_page(request: Request):
    return _render(request, "login.html")


@router.get("/live", include_in_schema=False)
async def live_page(request: Request):
    return _render(request, "live_services.html")


@router.get("/chat", include_in_schema=False)
async def chat_page(request: Request):
    return _render(request, "chat.html")


@router.get("/crons", include_in_schema=False)
async def crons_page(request: Request):
    return _render(request, "crons.html")


@router.get("/reminders", include_in_schema=False)
async def reminders_page(request: Request):
    return _render(request, "reminders.html")


@router.get("/persona", include_in_schema=False)
async def persona_page(request: Request):
    return _render(request, "persona_brain.html")


@router.get("/settings", include_in_schema=False)
async def settings_page(request: Request):
    return _render(request, "settings.html")
