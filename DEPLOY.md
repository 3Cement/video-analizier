# Deploy online — video-analizier

Aplikacja: wklejasz link YouTube → dostajesz podsumowanie (napisy albo Whisper ASR).

## Szybki start lokalnie

```bash
cp .env.example .env
# uzupełnij OPENAI_API_KEY (opcjonalnie, ale daje lepsze summary)
# na serwerach cloud często potrzebny YTDLP_PROXY lub YTDLP_COOKIES

docker compose up --build
```

UI: http://localhost:8000

## Render.com (Docker)

1. Połącz repo z Render.
2. Użyj `render.yaml` albo Web Service + Dockerfile.
3. Ustaw sekrety:
   - `OPENAI_API_KEY` — synteza LLM
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
| `OPENAI_API_KEY` | Lepsze, syntetyczne podsumowania |
| `YTDLP_PROXY` | Omija bot-check YouTube na IP chmury |
| `YTDLP_COOKIES` | Alternatywa / uzupełnienie do proxy |
| `WHISPER_MODEL` | `small`+ dla polskiego ASR |

Bez `OPENAI_API_KEY` aplikacja i tak działa — zwraca podsumowanie ekstraktywne z timestampami.
