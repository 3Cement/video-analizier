# Deploy online — video-analizier

Aplikacja: wklejasz link YouTube → dostajesz podsumowanie (napisy albo Whisper ASR).

## Szybki start lokalnie

```bash
cp .env.example .env
# uzupełnij OPENAI_API_KEY (opcjonalnie, ale daje lepsze summary)
# na serwerach cloud często potrzebny YTDLP_PROXY lub YTDLP_COOKIES

docker compose up --build
# uruchamia api (WORKER_MODE=true) + worker
```

UI: http://localhost:8000  
Ustaw `PUBLIC_BASE_URL=https://twoja-domena` dla poprawnych OG/canonical na stronach `/s/...`.

## Render.com (Docker)

1. Połącz repo z Render.
2. Użyj `render.yaml` albo Web Service + Dockerfile.
3. Ustaw sekrety:
   - `LLM_PROVIDER` + `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `CURSOR_API_KEY` — synteza LLM
   - `YTDLP_PROXY` — jeśli YouTube blokuje IP datacenter
4. Disk `/app/data` (już w `render.yaml`).

## VPS (Docker)

```bash
git clone <repo>
cd video-analizier
cp .env.example .env
nano .env
docker compose up -d --build
```

Opcjonalnie nginx + HTTPS (Caddy/Certbot) na port 8000.

## Co ustawić w `.env`

| Zmienna | Po co |
|---------|--------|
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `CURSOR_API_KEY` | Lepsze, syntetyczne podsumowania |
| `YTDLP_PROXY` | Omija bot-check YouTube na IP chmury |
| `YTDLP_COOKIES` | Alternatywa / uzupełnienie do proxy |
| `WHISPER_MODEL` | `small`+ dla polskiego ASR |

Bez klucza LLM aplikacja i tak działa — zwraca podsumowanie ekstraktywne z timestampami. Klucze można też wkleić w UI (Klucze LLM).


## Accounts / library

- Optional accounts: `POST /api/auth/register` and `/api/auth/login` (Bearer token).
- Set `AUTH_REQUIRED=true` to require login for API (except health/auth).
- Per-type daily limits: `DAILY_YOUTUBE_LIMIT`, `DAILY_AUDIO_LIMIT`, `DAILY_ARTICLE_LIMIT`.
- Library: `/api/library/search`, collections, tags, notes.
- PWA: `/manifest.webmanifest` + `/sw.js`.
- New ingest deps in image via `requirements.txt` (trafilatura, ebooklib, python-docx).


## Production hardening

- Login/register rate limits (in-memory per process).
- HttpOnly session cookie `va_session` (SameSite=Lax); Bearer still supported.
- Password reset: `POST /api/auth/password-reset/request` and `/confirm` (MVP returns `reset_link` when no SMTP).
- Job retries with backoff: `JOB_MAX_ATTEMPTS`, `JOB_RETRY_BASE_SECONDS`, stale reclaim `JOB_STALE_SECONDS`.
- Queue monitor: `GET /api/admin/queue` (requires `API_KEY` when configured).
- Smoke: `make smoke-docker`.
