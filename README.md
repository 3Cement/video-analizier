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
# opcjonalnie: LLM_PROVIDER + OPENAI/ANTHROPIC/CURSOR key, YTDLP_PROXY
docker compose up --build
```

UI: http://localhost:8000  
Deploy: patrz [DEPLOY.md](DEPLOY.md) (Render / VPS).

### Dev bez Dockera

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
cp .env.example .env
mkdir -p data/media
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
| `LLM_PROVIDER` | `openai` / `anthropic` / `cursor` |
| `OPENAI_API_KEY` | Klucz OpenAI |
| `ANTHROPIC_API_KEY` | Klucz Anthropic |
| `CURSOR_API_KEY` | Klucz OpenAI-compatible (jak w Cursor BYOK) |
| `OPENAI_MODEL` / `ANTHROPIC_MODEL` / `CURSOR_MODEL` | modele per provider |
| `WHISPER_MODEL` | `tiny`/`base`/`small`/`medium`/`large-v3` (dla PL produkcyjnie ≥ `small`) |
| `WHISPER_DEVICE` | `cpu` lub `cuda` |
| `WHISPER_LANGUAGE` | domyślnie `pl` |

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