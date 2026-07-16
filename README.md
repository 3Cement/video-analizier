# video-analizier

Online tool: **wklej link YouTube → dostaniesz podsumowanie** (także bez napisów, przez Whisper ASR).  
Działa też z PDF / tekstem / audio.

## Jak to działa

1. Wklejasz URL YouTube w UI.
2. Pobierane jest audio (`yt-dlp`); biorą się napisy albo idzie ASR PL.
3. Powstaje podsumowanie z kluczowymi wnioskami i timestampami `[mm:ss]`.
4. Możesz dopytać o szczegóły w materiale.

## Szybki start (online lokalnie)

```bash
cp .env.example .env
# ustaw PostgreSQL, Resend, Turnstile, domenę i jeden serwerowy klucz LLM
docker compose up --build
```

UI: http://localhost:8000  
Deploy produkcyjny: patrz [DEPLOY.md](DEPLOY.md) (VPS + PostgreSQL + worker + Caddy).

### Dev bez Dockera

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
cp .env.example .env
mkdir -p data/media
alembic upgrade head
PYTHONPATH=backend uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### CLI

```bash
# sprawdź napisy
PYTHONPATH=backend python -m app list-subs "https://www.youtube.com/watch?v=VIDEO_ID"

# pełna analiza (ASR jeśli brak napisów)
PYTHONPATH=backend python -m app analyze "https://www.youtube.com/watch?v=VIDEO_ID" \
  --summarize \
  --ask "Jakie są główne kroki?" \
  --save-transcript data/transcript.txt \
  --output data/result.json
```

## Konfiguracja

| Zmienna | Opis |
|---------|------|
| `LLM_PROVIDER` | `openai` / `anthropic` / `openrouter` (`cursor` tylko jako stary alias) |
| `OPENAI_API_KEY` | Klucz OpenAI |
| `ANTHROPIC_API_KEY` | Klucz Anthropic |
| `OPENROUTER_API_KEY` | Klucz OpenRouter; nie trafia do UI ani Vercela |
| `OPENAI_MODEL` / `ANTHROPIC_MODEL` / `OPENROUTER_MODEL` | modele per provider |
| `SINGLE_USER_EMAIL` | Jedyny adres, dla którego rejestracja jest otwarta w produkcji |
| `WHISPER_MODEL` | `tiny`/`base`/`small`/`medium`/`large-v3` (dla PL produkcyjnie ≥ `small`) |
| `WHISPER_DEVICE` | `cpu` lub `cuda` |
| `WHISPER_LANGUAGE` | domyślnie `pl` |
| `DATABASE_URL` | PostgreSQL używany przez API i workera |
| `RESEND_API_KEY` / `RESEND_FROM_EMAIL` | e-maile weryfikacji i resetu |
| `TURNSTILE_SITE_KEY` / `TURNSTILE_SECRET_KEY` | ochrona otwartej rejestracji |
| `ADMIN_API_KEY` | osobny klucz endpointów administracyjnych |

Konto musi zostać potwierdzone e-mailem. Sesja działa wyłącznie przez cookie HttpOnly; klucze LLM są wspólne, serwerowe i nie są ustawiane w przeglądarce.

## Testy

```bash
PYTHONPATH=backend pytest -q
```

## Pilot (film bez napisów / YouTube w chmurze)

Na IP datacenter YouTube często zwraca *Sign in to confirm you're not a bot*.
Pomaga `YTDLP_PROXY` i/lub `YTDLP_COOKIES`.

W `examples/`:
- `pilot_*` — ASR PL bez napisów (audio lokalne)
- `youtube_live_test.json` — live analiza filmu z kanału
  (*Treningi W Domu? Brutalna Prawda*)

## Uwagi prawne

Narzędzie służy do lokalnej analizy treści przez użytkownika. Nie redystrybuuj pobranego audio ani treści chronionych prawem autorskim.
