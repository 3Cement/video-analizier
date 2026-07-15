# Pilot examples

## `pilot_result.json` / `pilot_transcript.txt`

End-to-end run of the no-captions Polish pipeline:

1. Channel discovery via `yt-dlp --flat-playlist` on
   [Maciej Bielski / Ugot2BeStrong](https://www.youtube.com/@MaciejBielskiUgot2BeStrong/videos)
   (example video id: `tPsVjYR0tGY`).
2. Direct YouTube media download is currently blocked in this environment
   (`Sign in to confirm you're not a bot`).
3. To validate ASR → summary → Q&A without captions, a Polish spoken audio sample
   (`data/media/pilot_pl_no_captions.mp3`) was generated and processed with
   `faster-whisper` (`language=pl`).

### Reproduce

```bash
# optional regenerate audio
pip install gTTS && python scripts/generate_pilot_audio.py

PYTHONPATH=backend python -m app analyze-audio examples/pilot_pl_no_captions.mp3 \
  --title "Pilot PL bez napisów" \
  --summarize \
  --ask "Jakie są główne elementy treningu?" \
  --output examples/pilot_result.json \
  --save-transcript examples/pilot_transcript.txt
```

### Live YouTube test

`youtube_live_test.json` — cloud run for
`https://www.youtube.com/watch?v=tPsVjYR0tGY`
(*Treningi W Domu? Brutalna Prawda*, PL, no manual subs; auto-captions used).
On blocked datacenter IPs set `YTDLP_PROXY`.

### Real YouTube videos

```bash
# proxy and/or cookies help on cloud IPs
export YTDLP_PROXY=http://HOST:PORT
export YTDLP_COOKIES=/path/to/cookies.txt
PYTHONPATH=backend python -m app analyze "https://www.youtube.com/watch?v=VIDEO_ID" --summarize
```

### ASR smoke test

`asr_clip_test.json` — Whisper (`tiny`) on a 90s clip from the same video.
Shows that ASR path works end-to-end; for Polish production use captions when available or `WHISPER_MODEL=small+`.
