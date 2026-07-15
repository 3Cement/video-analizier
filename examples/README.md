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

### Real YouTube videos

Export cookies from a logged-in browser (Netscape format), then:

```bash
export YTDLP_COOKIES=/path/to/cookies.txt
PYTHONPATH=backend python -m app analyze "https://www.youtube.com/watch?v=VIDEO_ID" --summarize
```