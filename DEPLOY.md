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

## Railway.app (Docker, „podepnij GitHub i klikaj")

1. Wejdź na https://railway.app → **New Project** → **Deploy from GitHub repo**.
2. Wybierz repo `video-analizier` — Railway sam wykryje `Dockerfile` i `railway.json`.
3. W ustawieniach serwisu → **Variables** dodaj (opcjonalnie):
   - `LLM_PROVIDER` + `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` — lepsze podsumowania
   - `YTDLP_PROXY` — jeśli YouTube blokuje IP datacenter
   - `WHISPER_MODEL=small` (domyślne w `.env.example` może być za duże na mały plan)
4. W ustawieniach serwisu → **Volumes** podepnij wolumen pod `/app/data`
   (żeby baza i pliki przetrwały redeploy).
5. **Settings → Networking → Generate Domain** — dostajesz publiczny URL.

Kontener nasłuchuje na porcie z `PORT` (wstrzykiwany przez Railway); lokalnie
domyślnie 8000.

## Koyeb.com (Docker, darmowy tier)

1. https://app.koyeb.com → **Create Web Service** → **GitHub** → wybierz repo.
2. Builder: **Dockerfile**; health check: `/api/health` (port 8000).
3. Env vars jak wyżej. Uwaga: darmowy tier nie ma trwałego dysku —
   baza wyczyści się przy redeployu.

## Render.com (Docker)

1. Połącz repo z Render.
2. Użyj `render.yaml` albo Web Service + Dockerfile.
3. Ustaw sekrety:
   - `LLM_PROVIDER` + `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `CURSOR_API_KEY` — synteza LLM
   - `YTDLP_PROXY` — jeśli YouTube blokuje IP datacenter
4. Disk `/app/data` (już w `render.yaml`).

## VPS (Docker) — zalecana produkcja

Stack produkcyjny (`docker-compose.prod.yml`): api + worker + Caddy
(automatyczny certyfikat HTTPS z Let's Encrypt, gdy podasz domenę).

### 1. Instalacja (raz)

```bash
# na VPS (Ubuntu/Debian); pomiń jeśli Docker już jest
curl -fsSL https://get.docker.com | sh

git clone https://github.com/3Cement/video-analizier.git
cd video-analizier
cp .env.example .env
nano .env   # patrz sekcja "Co ustawić w .env" niżej
```

### 2. Start

```bash
# z domeną (najpierw ustaw rekord DNS A -> IP VPS-a):
DOMAIN=app.twoja-domena.pl docker compose -f docker-compose.prod.yml up -d --build

# bez domeny (HTTP na porcie 80, wejście po IP):
docker compose -f docker-compose.prod.yml up -d --build
```

UI: `https://app.twoja-domena.pl` (albo `http://IP-VPS-a`).

### 3. Utrzymanie

```bash
docker compose -f docker-compose.prod.yml logs -f          # logi
docker compose -f docker-compose.prod.yml ps               # status
git pull && DOMAIN=... docker compose -f docker-compose.prod.yml up -d --build  # update
```

Dane (baza SQLite + audio) żyją w `./data` na hoście — przeżywają
rebuild/restart. Backup: `tar czf backup.tar.gz data/`.

### Ważne na publicznym VPS

- **Dostęp**: bez `API_KEY` w `.env` aplikacja jest otwarta dla każdego, kto
  zna adres (a analizy zużywają Twój klucz LLM). Ustaw `API_KEY` albo chociaż
  niski `DAILY_SOURCE_LIMIT`.
- **YouTube bot-check**: IP VPS-a to IP datacenter — YouTube może wymagać
  `YTDLP_COOKIES` (wyeksportuj cookies z przeglądarki rozszerzeniem
  „Get cookies.txt") lub `YTDLP_PROXY` (proxy residential).
- **RAM**: Whisper `small` potrzebuje ~2 GB RAM. Na małym VPS ustaw
  `WHISPER_MODEL=base` (szybciej, trochę gorsza jakość PL) albo dodaj swap.
- `PUBLIC_BASE_URL=https://app.twoja-domena.pl` — poprawne linki „Udostępnij".

## Co ustawić w `.env`

| Zmienna | Po co |
|---------|--------|
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `CURSOR_API_KEY` | Lepsze, syntetyczne podsumowania |
| `YTDLP_PROXY` | Omija bot-check YouTube na IP chmury |
| `YTDLP_COOKIES` | Alternatywa / uzupełnienie do proxy |
| `WHISPER_MODEL` | `small`+ dla polskiego ASR |

Bez klucza LLM aplikacja i tak działa — zwraca podsumowanie ekstraktywne z timestampami. Klucze można też wkleić w UI (Klucze LLM).
