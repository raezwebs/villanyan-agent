# ⬡ VILLANYAN-AGENT

> **VILLANYAN Personal Agent Dashboard** — panel zarządzania agentem Hermes na Raspberry Pi 5  
> Python-only. Zero Node.js. Zero build step. Jeden proces.

---

## Jedno polecenie

```bash
pip install -r requirements.txt && cp .env.example .env && python app.py
```

Otwórz `http://localhost:7890` w przeglądarce. Gotowe.

---

## Filozofia

Jeden język — Python. Zero zależności JS, zero build stepu, zero `node_modules`.
Cały frontend to szablony Jinja2 renderowane po stronie serwera, interaktywność przez HTMX,
stan UI przez Alpine.js (~3KB), stylowanie przez własny CSS (12KB, 259 klas).

| Obszar | Stack |
|--------|-------|
| Język | Python 3.11+ — jedyny język w projekcie |
| Backend | FastAPI + Uvicorn (async) |
| Frontend | Jinja2 szablony + HTMX + Alpine.js |
| CSS | Własny CSS, ~300 klas, zero frameworków |
| Baza danych | SQLite + async SQLAlchemy 2.0 (WAL mode) |
| Autoryzacja | JWT (access 15min + refresh 7 dni) |
| Rate limiting | slowapi |

---

## Architektura

```
┌──────────────────────────────────────────────────────┐
│                    app.py                            │
│   python app.py --port 7890 --reload                 │
├──────────────────────────────────────────────────────┤
│              FastAPI (jeden proces)                    │
│                                                       │
│   backend/ ─┬── main.py          ← create_app()      │
│              ├── core/            ← db, modele, auth  │
│              ├── routes/          ← 17 modułów API    │
│              ├── templates/       ← 9 szablonów HTML  │
│              ├── static/          ← CSS + JS          │
│              └── services/        ← logika biznesowa  │
├──────────────────────────────────────────────────────┤
│  Hermes Agent / Obsidian / System / Docker            │
│                                                       │
│  ~/.hermes/state.db  — sesje i wiadomości agenta     │
│  ~/obsidian-vault/   — Obsidian vault                 │
│  ~/cloudilla/        — chmura willańska               │
│  systemd, Docker, UFW, Ollama                         │
└──────────────────────────────────────────────────────┘
```

---

## Struktura plików

```
villanyan-agent/
├── app.py                          # Entry point
├── backend/
│   ├── main.py                     # create_app()
│   ├── core/
│   │   ├── db.py                   # SQLAlchemy async
│   │   ├── models.py               # ORM modele
│   │   ├── schemas.py              # Pydantic
│   │   └── security.py             # JWT + bcrypt
│   ├── routes/
│   │   ├── auth.py                 # logowanie JWT
│   │   ├── system.py               # CPU, RAM, dysk, temp
│   │   ├── docker.py               # Docker API
│   │   ├── sessions.py             # sesje Hermes
│   │   ├── hermes.py               # LLM chat
│   │   ├── obsidian.py             # Obsidian vault
│   │   ├── cloud.py                # cloudilla (files)
│   │   ├── github.py               # GitHub projekty
│   │   ├── cron.py                 # CRUD cron jobów
│   │   ├── reminders.py            # przypomnienia DB
│   │   ├── network.py              # porty TCP/UDP
│   │   ├── costs.py                # koszty API
│   │   ├── notifications.py        # SSE + powiadomienia
│   │   ├── memory.py               # wersje plików
│   │   ├── compat.py               # legacy API
│   │   └── pages.py                # strony HTML
│   ├── templates/
│   │   ├── base.html               # layout + sidebar
│   │   ├── login.html              # logowanie
│   │   ├── dashboard.html          # Dashboard
│   │   ├── live_services.html      # LIVE
│   │   ├── chat.html               # Czat
│   │   ├── crons.html              # Automatyzacje
│   │   ├── reminders.html          # Przypomnienia
│   │   ├── persona_brain.html      # Mózg Persony
│   │   ├── settings.html           # Ustawienia
│   │   └── partials/               # HTMX partials
│   └── static/
│       ├── style.css               # CSS (12KB)
│       ├── htmx.min.js             # HTMX (50KB)
│       └── alpine.min.js           # Alpine.js (44KB)
├── requirements.txt                # Zależności Python
├── .env.example                    # Wzór konfiguracji
└── README.md
```

27 plików .py, 9 szablonów HTML, 3 pliki statyczne. Zero `package.json`, zero `node_modules`, zero build step.

---

## Frontend — widoki

| Widok | URL | Opis |
|-------|-----|------|
| Dashboard | `/` | Status systemu, cloudilla, GitHub projekty |
| Status LIVE | `/live` | Docker, porty, Obsidian, koszty |
| Czat | `/chat` | Rozmowa z Hermesem |
| Automatyzacje | `/crons` | CRUD cron jobów |
| Przypomnienia | `/reminders` | Lista + dodawanie |
| Mózg Persony | `/persona` | Edytor plików agenta |
| Ustawienia | `/settings` | Konfiguracja |
| Logowanie | `/login` | Password-only |

Frontend działa przez:
- **HTMX** — interaktywność bez pisania JavaScript (partial page updates, SSE, auto-refresh)
- **Alpine.js** — stan UI (modale, toggles, sidebar)
- **Własny CSS** — ~300 klas, dark theme, akcent #00D18B, custom scrollbar

---

## Backend — endpointy API

### Autoryzacja
| Metoda | Endpoint | Opis |
|--------|----------|------|
| POST | `/api/auth/login` | Logowanie (password-only) |
| POST | `/api/auth/refresh` | Odświeżenie tokenu |
| POST | `/api/auth/logout` | Wylogowanie |
| GET | `/api/auth/check` | Weryfikacja tokena |
| GET | `/api/auth/me` | Profil użytkownika |

### System
| Metoda | Endpoint | Opis |
|--------|----------|------|
| GET | `/api/health` | Health check |
| GET | `/api/system/metrics` | CPU, RAM, dysk, temperatura |
| POST | `/api/system/service` | Start/stop/restart usługi systemd |

### Docker
| Metoda | Endpoint | Opis |
|--------|----------|------|
| GET | `/api/docker/containers` | Lista kontenerów |
| POST | `/api/docker/containers/{id}/{action}` | start/stop/restart |

### Sesje i czat
| Metoda | Endpoint | Opis |
|--------|----------|------|
| GET | `/api/sessions` | Lista sesji |
| POST | `/api/sessions` | Utwórz sesję |
| GET | `/api/sessions/{id}/messages` | Wiadomości sesji |
| POST | `/api/sessions/{id}/send` | Wyślij wiadomość |

### Hermes AI
| Metoda | Endpoint | Opis |
|--------|----------|------|
| POST | `/api/hermes/message` | Wyślij do LLM (Gemini → OpenAI → fallback) |
| GET | `/api/hermes/agent` | Status agenta |
| GET/PUT | `/api/hermes/agent-memory/{name}` | Czytaj/zapisz plik agenta |

### Obsidian
| Metoda | Endpoint | Opis |
|--------|----------|------|
| GET | `/api/obsidian/status` | Status vaultu |
| GET | `/api/obsidian/reminders` | Przypomnienia z vaultu |
| POST | `/api/obsidian/reminders` | Dodaj przypomnienie |
| POST | `/api/obsidian/reminders/{id}/toggle` | Przełącz status |
| DELETE | `/api/obsidian/reminders/{id}` | Usuń |

### Cloudilla
| Metoda | Endpoint | Opis |
|--------|----------|------|
| GET | `/api/cloud/files` | Lista plików |
| POST | `/api/cloud/upload` | Upload pliku |
| POST | `/api/cloud/mkdir` | Utwórz katalog |
| DELETE | `/api/cloud/files/{path}` | Usuń plik/katalog |

### Cron
| Metoda | Endpoint | Opis |
|--------|----------|------|
| GET/POST | `/api/cron/jobs` | Lista/utwórz cron job |
| GET/PATCH/DELETE | `/api/cron/jobs/{id}` | CRUD |
| POST | `/api/cron/jobs/{id}/run` | Uruchom ręcznie |

### Sieć
| Metoda | Endpoint | Opis |
|--------|----------|------|
| GET | `/api/network/ports` | Otwarte porty TCP/UDP |

### Inne
| Metoda | Endpoint | Opis |
|--------|----------|------|
| GET | `/api/github/projects` | Repozytoria GitHub |
| GET | `/api/ollama/models` | Modele Ollama |
| GET | `/api/costs` | Koszty API |
| GET | `/api/notifications` | Powiadomienia |
| GET | `/api/notifications/stream` | SSE streaming |
| GET/POST/DELETE | `/api/memory` | Wersje plików pamięci |

---

## Deployment

### Wymagania
- Raspberry Pi 5, Debian 13+ (Trixie)
- Python 3.11+
- Hermes Agent (`~/.hermes/state.db`)
- Docker (opcjonalnie)

### Instalacja
```bash
git clone https://github.com/raezwebs/villanyan-agent.git
cd villanyan-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Uruchom
python app.py
# → http://localhost:7890

# Z auto-reload (dev)
python app.py --reload
```

### Systemd
```bash
cp deploy/villanyan-agent.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now villanyan-agent
```

### Nginx Proxy Manager
Dodaj proxy: `villanyan.paninello.pl` → `localhost:7890`, SSL.

---

## Zmienne środowiskowe

| Zmienna | Domyślnie | Opis |
|---------|-----------|------|
| `VILLANYAN_PASSWORD` | (random) | Hasło do logowania |
| `SECRET_KEY` | (random) | Klucz JWT |
| `DATABASE_URL` | `sqlite+aiosqlite:///./villanyan-agent.db` | URL bazy danych |
| `VILLANYAN_PORT` | `7890` | Port |
| `DEBUG` | `true` | Tryb debugowania |
| `ALLOWED_ORIGINS` | `*` | CORS |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Czas życia access tokena |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Czas życia refresh tokena |
| `BCRYPT_ROUNDS` | `12` | Koszt hashowania |
| `GEMINI_API_KEY` | — | Klucz Google Gemini |
| `OPENAI_API_KEY` | — | Klucz OpenAI |
| `OLLAMA_API_URL` | `http://192.168.1.109:11434` | URL Ollama |

---

## Bezpieczeństwo

- JWT Bearer — access token 15 min + refresh token 7 dni, JTI + SHA256 hash
- Bcrypt 12 roundów — hashowanie haseł
- Rate limiting — slowapi (10/min login)
- Shell injection prevention — wszystkie `subprocess.run()` z listą argumentów
- Path traversal protection — `resolve() + relative_to()` w cloud endpoints
- Path traversal prevention — `pathlib.Path(name).name` w hermes/agent-memory

---

## Rozwiązywanie problemów

| Problem | Rozwiązanie |
|---------|-------------|
| Backend nie startuje | `pip install -r requirements.txt` + sprawdź `.env` |
| Port 7890 zajęty | `sudo lsof -ti:7890 \| xargs sudo kill` |
| 401 na dashboardzie | Zaloguj się ponownie (token wygasł) |
| Stara wersja w przeglądarce | Ctrl+F5 (cache bypass) |
| Chat nie odpowiada | Sprawdź `GEMINI_API_KEY` / `OPENAI_API_KEY` w `.env` |

---

## Licencja

MIT — używaj, modyfikuj, dziel się.

Autor: [@raezwebs](https://github.com/raezwebs)
Dashboard: [villanyan.paninello.pl](https://villanyan.paninello.pl)
