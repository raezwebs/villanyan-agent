# ⬡ VILLANYAN-AGENT 3.0

> **VILLANYAN Personal Agent Dashboard** — w pełni Pythonowy panel zarządzania agentem Hermes na Raspberry Pi 5
> Live: [`https://villanyan.paninello.pl`](https://villanyan.paninello.pl)

**Zero Node.js. Zero npm. Zero build step. Jeden proces.**

---

## Spis treści

- [Filozofia](#filozofia)
- [Jedno polecenie do uruchomienia](#jedno-polecenie-do-uruchomienia)
- [Architektura](#architektura)
- [Struktura plików](#struktura-plików)
- [Frontend](#frontend)
- [Backend — endpointy REST](#backend--endpointy-rest)
- [Stack technologiczny](#stack-technologiczny)
- [Deployment](#deployment)
- [Zmienne środowiskowe](#zmienne-środowiskowe)
- [Bezpieczeństwo](#bezpieczeństwo)
- [Licencja](#licencja)

---

## Filozofia

> **Jeden język. Zero build. Minimum zależności.**

villanyan-agent 3.0 to kompletne przepisanie dashboardu z React/TypeScript na czysty Python.
Cały frontend to **szablony Jinja2 renderowane po stronie serwera**, interaktywność przez **HTMX**
(partial page updates), stan UI przez **Alpine.js** (~3KB), a stylowanie przez **Tailwind CSS v4 + DaisyUI**.

| Obszar | Przed (2.0) | Po (3.0) |
|--------|-------------|----------|
| Języki | Python + JavaScript + TypeScript | **tylko Python** |
| Frontend | React 19 + 200KB JS bundle | **Jinja2 + HTMX + Alpine.js (~30KB)** |
| Build step | `npm install` + `npm run build` | **zero** |
| Zależności JS | 30k plików, ~200MB node_modules | **0 plików** |
| Procesy | Backend (uvicorn) + Dev (vite) | **jeden proces** |

---

## Jedno polecenie do uruchomienia

```bash
pip install -r requirements.txt && cp .env.example .env && python app.py
```

Otwórz `http://localhost:7890` w przeglądarce. Gotowe.

---

## Architektura

```
┌──────────────────────────────────────────────────────────────────┐
│                     app.py (jedyny entry point)                   │
│                                                                   │
│   uvicorn.run(app, host="0.0.0.0", port=7890)                    │
│                                                                   │
├──────────────────────────────────────────────────────────────────┤
│                        FastAPI aplikacja                          │
│                                                                   │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │  Jinja2Templates — szablony HTML renderowane po stronie │    │
│   │  serwera (SSR). Zero JS framework.                      │    │
│   │  Pliki: app/templates/*.html                             │    │
│   └─────────────────────────────────────────────────────────┘    │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │  HTMX — interaktywność przez atrybuty HTML              │    │
│   │  hx-get, hx-post, hx-target, hx-trigger, hx-swap       │    │
│   │  Partial page updates — bez pisania JS                  │    │
│   └─────────────────────────────────────────────────────────┘    │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │  Alpine.js — stan UI tam gdzie HTMX nie wystarcza       │    │
│   │  x-data, x-bind, x-on, x-show, x-for, x-model          │    │
│   │  ~3KB gzip — modale, toggles, zakładki, formularze     │    │
│   └─────────────────────────────────────────────────────────┘    │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │  Tailwind CSS v4 + DaisyUI                              │    │
│   │  @import "tailwindcss" + @theme w static/style.css      │    │
│   │  DaisyUI: karty, buttony, badge, tabela, modal, tabs   │    │
│   └─────────────────────────────────────────────────────────┘    │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │  API REST — te same endpointy co w wersji 2.0           │    │
│   │  + partial endpoints (HTMX) zwracające HTML fragmenty   │    │
│   │  + SSE / WebSocket dla real-time                        │    │
│   └─────────────────────────────────────────────────────────┘    │
├──────────────────────────────────────────────────────────────────┤
│            Hermes Agent / Obsidian / System / cloudilla          │
│                                                                   │
│   ~/.hermes/state.db — sesje i wiadomości agenta                 │
│   ~/.hermes/ — SOUL.md, MEMORY.md, USER.md, AGENTS.md           │
│   ~/obsidian-vault/ — Obsidian vault (MCP + REST API :27124)     │
│   systemd --user: villanyan, obsidian, novnc                       │
│   Docker (przez docker-py), Ollama, cloudilla (~/cloudilla/)     │
│   SQLite (WAL mode) — baza danych backendu                       │
└──────────────────────────────────────────────────────────────────┘
```

---

## Struktura plików

```
villanyan-agent/
├── app.py                        # ➡ JEDEN entry point (python app.py)
├── backend/
│   ├── __init__.py               # create_app() factory
│   ├── config.py                 # pydantic-settings (wszystkie env vars)
│   ├── main.py                   # lifespan, CORS, routery, SPA fallback
│   │
│   ├── routes/                   # API endpointy
│   │   ├── __init__.py
│   │   ├── auth.py               # JWT login/logout/refresh/register
│   │   ├── system.py             # CPU, RAM, temp, dysk, uptime
│   │   ├── docker.py             # Docker przez docker-py
│   │   ├── sessions.py           # sesje Hermes (state.db)
│   │   ├── hermes.py             # LLM chat
│   │   ├── obsidian.py           # Obsidian REST + reminders
│   │   ├── cloud.py              # cloudilla (CRUD plików)
│   │   ├── github.py             # gh CLI
│   │   ├── cron.py               # cron joby w DB
│   │   ├── reminders.py          # przypomnienia w DB
│   │   ├── network.py            # porty (ss + /proc)
│   │   ├── costs.py              # koszty API
│   │   ├── notifications.py      # SSE + powiadomienia
│   │   ├── memory.py             # wersje plików pamięci
│   │   └── compat.py             # legacy endpointy
│   │
│   ├── templates/                # ➡ Szablony Jinja2 (frontend)
│   │   ├── base.html             # layout: sidebar, topbar, dark theme
│   │   ├── login.html            # strona logowania
│   │   ├── dashboard.html        # Dashboard
│   │   ├── live_services.html    # LIVE
│   │   ├── chat.html             # Czat z Hermesem
│   │   ├── crons.html            # Automatyzacje/Crony
│   │   ├── reminders.html        # Przypomnienia
│   │   ├── persona_brain.html    # Mózg Persony
│   │   ├── settings.html         # Ustawienia
│   │   │
│   │   └── partials/             # HTMX partials (fragmenty HTML)
│   │       ├── system_metrics.html
│   │       ├── docker_list.html
│   │       ├── port_table.html
│   │       ├── session_list.html
│   │       ├── chat_messages.html
│   │       ├── notification_list.html
│   │       ├── cron_table.html
│   │       └── reminder_list.html
│   │
│   ├── static/                   # CSS + JS (minimalne)
│   │   ├── style.css             # @import "tailwindcss" + @theme + DaisyUI
│   │   ├── htmx.min.js           # HTMX (dołączony, żaden CDN)
│   │   ├── alpine.min.js         # Alpine.js (dołączony)
│   │   └── favicon.ico
│   │
│   ├── core/                     # Rdzeń aplikacji
│   │   ├── __init__.py
│   │   ├── db.py                 # async SQLAlchemy + aiosqlite
│   │   ├── models.py             # ORM modele (User, CronJob, Reminder, itp.)
│   │   ├── schemas.py            # Pydantic schemas
│   │   └── security.py           # JWT, bcrypt, rate limit
│   │
│   ├── services/                 # Logika biznesowa (oddzielona od routes)
│   │   ├── __init__.py
│   │   ├── system_collector.py   # Metryki systemowe (psutil + vcgencmd)
│   │   ├── docker_service.py     # Docker przez docker-py
│   │   ├── hermes_client.py      # Klient Hermes CLI
│   │   ├── obsidian_client.py    # Klient Obsidian REST API
│   │   └── github_client.py      # Klient gh CLI
│   │
│   └── speech/                   # Mowa (Web Speech API proxy)
│       ├── __init__.py
│       ├── stt.py                # Speech-to-Text (Whisper.cpp przez subprocess)
│       └── tts.py                # Text-to-Speech (edge-tts / pyttsx3)
│
├── tests/                        # Testy
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_routes/
│   └── test_templates/
│
├── requirements.txt              # Wszystkie zależności
├── .env                          # Konfiguracja (SECRET_KEY, VILLANYAN_PASSWORD, itp.)
├── .env.example                  # Wzór .env
├── villanyan-agent.db             # SQLite (generowany automatycznie)
├── deploy/
│   └── villanyan-agent.service    # systemd user service
└── README.md                     # Ten plik
```

**34 pliki** (w tym 13 szablonów HTML, 8 partiali, 4 pliki statyczne). Zero package.json, zero node_modules, zero build step.

---

## Frontend

### Technologie

| Technologia | Wersja | Rozmiar | Rola |
|-------------|--------|---------|------|
| Jinja2 | 3.1.x | wbudowany | Renderowanie HTML po stronie serwera |
| HTMX | 2.x | ~14KB gzip | Interaktywność, partial page updates, SSE |
| Alpine.js | 3.x | ~3KB gzip | Stan UI, modale, toggles, formularze |
| Tailwind CSS | 4.x | ~27KB po purge | Utility-first CSS |
| DaisyUI | 5.x | ~8KB po purge | Pre-built komponenty (karty, buttony, badge) |

### Widoki

| Widok | URL | Plik szablonu | Opis |
|-------|-----|---------------|------|
| Login | `/login` | `login.html` | Logowanie hasłem (password-only) |
| Dashboard | `/` | `dashboard.html` | Status systemu, cloudilla, GitHub projekty |
| LIVE | `/live` | `live_services.html` | Docker, systemd, porty, Obsidian, koszty |
| Chat | `/chat` | `chat.html` | Czat z Hermesem (SSE + HTMX polling) |
| Crony | `/crons` | `crons.html` | CRUD cron jobów |
| Reminders | `/reminders` | `reminders.html` | Zarządzanie przypomnieniami |
| Persona Brain | `/persona` | `persona_brain.html` | Edytor SOUL.md/MEMORY.md/USER.md/AGENTS.md |
| Settings | `/settings` | `settings.html` | Ustawienia (modele, język, limity) |

### Jak działa interaktywność

**Przykład 1 — auto-odświeżanie metryk (HTMX):**
```html
<div hx-get="/partials/system-metrics" hx-trigger="every 30s" hx-swap="innerHTML">
  {% include "partials/system_metrics.html" %}
</div>
```

**Przykład 2 — expandable tile (Alpine.js):**
```html
<div x-data="{ open: false }" class="card">
  <button @click="open = !open" class="btn btn-ghost">
    Kontenery Docker
  </button>
  <div x-show="open" x-transition
       hx-get="/partials/docker-list" hx-trigger="load">
  </div>
</div>
```

**Przykład 3 — formularz z HTMX:**
```html
<form hx-post="/api/cron/jobs" hx-target="#cron-table" hx-swap="outerHTML">
  <input type="text" name="name" class="input input-bordered" />
  <input type="text" name="schedule" class="input input-bordered" />
  <button type="submit" class="btn btn-primary">Dodaj</button>
</form>
```

**Przykład 4 — SSE dla czatu:**
```html
<div hx-ext="sse" sse-connect="/api/chat/stream?session_id={{ session.id }}"
     sse-swap="message" id="chat-messages">
  {% include "partials/chat_messages.html" %}
</div>
```

---

## Backend — endpointy REST

### Autoryzacja

| Metoda | Endpoint | Auth | Opis |
|--------|----------|------|------|
| POST | `/api/auth/login` | — | Logowanie (password-only lub user+pass) |
| POST | `/api/auth/refresh` | — | Odświeżenie tokenu |
| POST | `/api/auth/logout` | JWT | Unieważnienie refresh tokena |
| GET | `/api/auth/check` | JWT | Weryfikacja tokena |
| GET | `/api/auth/me` | JWT | Profil użytkownika |

### System

| Metoda | Endpoint | Auth | Opis |
|--------|----------|------|------|
| GET | `/api/health` | — | Health check |
| GET | `/api/status` | JWT | Wszystkie dane systemowe (cache 30s) |
| GET | `/api/system/metrics` | JWT | CPU, RAM, temp, load, uptime, historia 24h |
| POST | `/api/system/service` | JWT | Start/stop/restart systemd service |
| GET | `/api/config` | JWT | Konfiguracja dashboardu |

### Docker

| Metoda | Endpoint | Auth | Opis |
|--------|----------|------|------|
| GET | `/api/docker/containers` | JWT | Lista kontenerów + stats + health |
| POST | `/api/docker/containers/{id}/{action}` | JWT | start/stop/restart |

### Sieć

| Metoda | Endpoint | Auth | Opis |
|--------|----------|------|------|
| GET | `/api/network/ports` | JWT | Otwarte porty |
| POST | `/api/ufw/port` | JWT | Otwórz/zablokuj port UFW |

### Obsidian

| Metoda | Endpoint | Auth | Opis |
|--------|----------|------|------|
| GET | `/api/obsidian/status` | — | Status Obsidian REST API |
| GET | `/api/obsidian/reminders` | JWT | Przypomnienia z vault |
| POST | `/api/obsidian/reminders` | JWT | Dodaj przypomnienie |
| POST | `/api/obsidian/reminders/{id}/toggle` | JWT | Przełącz status |
| DELETE | `/api/obsidian/reminders/{id}` | JWT | Usuń z vault |

### Sesje i czat

| Metoda | Endpoint | Auth | Opis |
|--------|----------|------|------|
| GET | `/api/sessions` | — | Lista sesji z Hermes state.db |
| POST | `/api/sessions` | — | Utwórz sesję |
| GET | `/api/sessions/{id}/messages` | — | Wiadomości sesji |
| POST | `/api/sessions/{id}/send` | — | Wyślij wiadomość |
| GET | `/api/chat/stream` | — | SSE dla czatu |

### Hermes AI

| Metoda | Endpoint | Auth | Opis |
|--------|----------|------|------|
| POST | `/api/hermes/message` | — | Wyślij do LLM (Gemini → OpenAI → fallback) |
| GET | `/api/hermes/agent` | JWT | Status agenta Hermes |
| GET | `/api/hermes/agent-memory` | JWT | Lista plików agenta |
| GET/PUT | `/api/hermes/agent-memory/{name}` | JWT | Czytaj/zapisz plik agenta |

### Cron

| Metoda | Endpoint | Auth | Opis |
|--------|----------|------|------|
| GET/POST | `/api/cron/jobs` | JWT | Lista/utwórz cron job |
| GET/PATCH/DELETE | `/api/cron/jobs/{id}` | JWT | CRUD cron joba |
| POST | `/api/cron/jobs/{id}/run` | JWT | Uruchom ręcznie |

### Cloudilla

| Metoda | Endpoint | Auth | Opis |
|--------|----------|------|------|
| GET | `/api/cloud/files` | — | Lista plików |
| POST | `/api/cloud/upload` | — | Upload pliku |
| POST | `/api/cloud/mkdir` | — | Utwórz katalog |
| DELETE | `/api/cloud/files/{path}` | — | Usuń plik/katalog |

### Inne

| Metoda | Endpoint | Auth | Opis |
|--------|----------|------|------|
| GET | `/api/github/projects` | JWT | Repozytoria GitHub |
| GET | `/api/ollama/models` | JWT | Modele Ollama |
| GET | `/api/costs` | JWT | Koszty API |
| GET | `/api/notifications` | JWT | Powiadomienia |
| POST | `/api/notifications/read` | JWT | Oznacz jako przeczytane |
| GET | `/api/stream` | — | SSE events streaming |

### HTMX partials (dodatkowe, dla frontendu)

| Metoda | Endpoint | Opis |
|--------|----------|------|
| GET | `/partials/system-metrics` | Kafelki CPU/RAM/temp (co 30s) |
| GET | `/partials/docker-list` | Lista kontenerów (expand) |
| GET | `/partials/port-table` | Tabela portów (expand) |
| GET | `/partials/session-list` | Lista sesji (sidebar) |
| GET | `/partials/notification-list` | Panel powiadomień |
| GET | `/partials/cron-table` | Tabela cron jobów |
| GET | `/partials/reminder-list` | Lista przypomnień |

---

## Stack technologiczny

| Warstwa | Technologia | Wersja | Rozmiar |
|---------|------------|--------|---------|
| Język | Python | 3.11+ | — |
| Framework | FastAPI | 0.115+ | — |
| Serwer ASGI | Uvicorn | 0.30+ | — |
| ORM | SQLAlchemy | 2.0+ (async) | — |
| DB | SQLite (aiosqlite, WAL) | — | — |
| Auth | PyJWT + bcrypt | — | — |
| Rate limit | slowapi | — | — |
| Szablony | Jinja2 | 3.1.x | wbudowany |
| Frontend interakcja | HTMX | 2.x | ~14KB gzip |
| Frontend stan UI | Alpine.js | 3.x | ~3KB gzip |
| CSS utility | Tailwind CSS | 4.x | ~27KB po purge |
| Komponenty UI | DaisyUI | 5.x | ~8KB po purge |
| Docker API | docker-py | 7.x | — |
| System metrics | psutil | 7.x | — |
| HTTP klient | httpx | 0.28+ | — |
| Type checking | mypy | 2.x | dev-only |
| Testy | pytest | — | dev-only |

**Łączny rozmiar JS w przeglądarce:** ~17KB (HTMX 14KB + Alpine 3KB).  
**Porównanie:** wersja 2.0 (React) — ~200KB JS bundle.

---

## Deployment

### Wymagania

- Raspberry Pi 5, Debian 13+ (Trixie)
- Python 3.11+
- Hermes Agent (`~/.hermes/state.db`)
- systemd --user
- Docker (opcjonalnie)
- UFW (opcjonalnie)
- Obsidian (opcjonalnie, dla integracji vault)

### Instalacja

```bash
# 1. Klonowanie
git clone https://github.com/raezwebs/villanyan-agent.git
cd villanyan-agent

# 2. Python
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Konfiguracja
cp .env.example .env
# Edytuj .env — ustaw VILLANYAN_PASSWORD i SECRET_KEY

# 4. Uruchom
python app.py
# Otwórz http://localhost:7890

# 5. Systemd
cp deploy/villanyan-agent.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now villanyan-agent

# 6. Nginx Proxy Manager
# Dodaj proxy: villanyan.paninello.pl → localhost:7890, SSL
```

### Development

```bash
# Uruchom z auto-reload
python app.py --reload

# Type checking
mypy backend/ --strict

# Testy
pytest tests/
```

---

## Zmienne środowiskowe

| Zmienna | Domyślnie | Wymagany | Opis |
|---------|-----------|----------|------|
| `VILLANYAN_PASSWORD` | (random) | ✅ | Hasło do logowania |
| `SECRET_KEY` | (random) | ⚠️ | Klucz JWT |
| `DATABASE_URL` | `sqlite+aiosqlite:///./villanyan-agent.db` | — | URL bazy |
| `VILLANYAN_PORT` | `7890` | — | Port |
| `DEBUG` | `true` | — | Tryb debug |
| `ALLOWED_ORIGINS` | `*` | — | CORS |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | — | Czas życia access tokena |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | — | Czas życia refresh tokena |
| `BCRYPT_ROUNDS` | `12` | — | Koszt hashowania |
| `GEMINI_API_KEY` | — | — | Klucz Google Gemini |
| `OPENAI_API_KEY` | — | — | Klucz OpenAI |
| `OLLAMA_API_URL` | `http://192.168.1.109:11434` | — | URL Ollama |

---

## Bezpieczeństwo

- **JWT Bearer** — access token 15 min + refresh token 7 dni, JTI + SHA256 hash
- **Bcrypt 12 roundów** — hashowanie haseł
- **Rate limiting** — slowapi (10/min login)
- **shell=False** — wszystkie `subprocess.run()` z listą argumentów
- **Path traversal protection** — `resolve() + relative_to()` w cloud endpoints
- **Whitelist** — tylko dozwolone pliki agenta (SOUL.md, MEMORY.md, USER.md, AGENTS.md)
- **mypy --strict** — 0 błędów typów

---

## Licencja

MIT — używaj, modyfikuj, dziel się.

Autor: [@raezwebs](https://github.com/raezwebs)
Dashboard: [villanyan.paninello.pl](https://villanyan.paninello.pl)
