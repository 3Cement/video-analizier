# video-analizier

Narzędzie w stylu NotebookLM: analizuje źródła (YouTube bez napisów, audio, PDF, tekst), buduje transkrypt ze znacznikami czasu i generuje podsumowania oraz odpowiedzi z cytowaniami `[mm:ss]`.

## Jak to działa

1. **Ingest** — URL YouTube (`yt-dlp`) albo upload PDF/TXT/audio.
2. **Tekst** — napisy YouTube jeśli są; w przeciwnym razie ASR `faster-whisper` (`language=pl`).
3. **Indeks** — segmenty z timestampami w SQLite.
4. **LLM** — briefing / FAQ / Q&A tylko na podstawie źródła (wymaga `OPENAI_API_KEY`).

## Szybki start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
cp .env.example .env   # uzupełnij OPENAI_API_KEY
mkdir -p data/media

# API + UI
PYTHONPATH=backend uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

UI: http://localhost:8000  
API docs: http://localhost:8000/docs

### Docker

```bash
cp .env.example .env
docker compose up --build
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
| `OPENAI_API_KEY` | Klucz do LLM (summary + Q&A) |
| `OPENAI_BASE_URL` | Kompatybilne API OpenAI |
| `OPENAI_MODEL` | domyślnie `gpt-4o-mini` |
| `WHISPER_MODEL` | `tiny`/`base`/`small`/`medium`/`large-v3` |
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