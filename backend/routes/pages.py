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
    return _render(request, "dashboard.html", active_view="dashboard")


@router.get("/login", include_in_schema=False)
async def login_page(request: Request):
    return _render(request, "login.html", active_view="login")


@router.get("/live", include_in_schema=False)
async def live_page(request: Request):
    return _render(request, "live_services.html", active_view="live")


@router.get("/chat", include_in_schema=False)
async def chat_page(request: Request):
    return _render(request, "chat.html", active_view="chat")


@router.get("/crons", include_in_schema=False)
async def crons_page(request: Request):
    return _render(request, "crons.html", active_view="crons")


@router.get("/reminders", include_in_schema=False)
async def reminders_page(request: Request):
    return _render(request, "reminders.html", active_view="reminders")


@router.get("/persona", include_in_schema=False)
async def persona_page(request: Request):
    return _render(request, "persona_brain.html", active_view="persona")


@router.get("/settings", include_in_schema=False)
async def settings_page(request: Request):
    return _render(request, "settings.html", active_view="settings")
