from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

import yt_dlp

from app.ingest.captions import CaptionSegment, clean_caption_text, normalize_caption_stream

T = TypeVar("T")


@dataclass
class YouTubeIngestResult:
    title: str
    url: str
    video_id: str
    duration_seconds: Optional[float]
    audio_path: Optional[Path]
    captions: list[CaptionSegment]
    caption_lang: Optional[str]


_VTT_TS = re.compile(
    r"(?:(\d{2}):)?(\d{2}):(\d{2})[.,](\d{3})\s*-->\s*(?:(\d{2}):)?(\d{2}):(\d{2})[.,](\d{3})"
)


def _ts_to_seconds(h: Optional[str], m: str, s: str, ms: str) -> float:
    hours = int(h or 0)
    return hours * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_vtt(content: str) -> list[CaptionSegment]:
    segments: list[CaptionSegment] = []
    blocks = re.split(r"\n\s*\n", content.strip())
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        ts_line = None
        text_lines: list[str] = []
        for ln in lines:
            if "-->" in ln:
                ts_line = ln
            elif ts_line is not None and not ln.isdigit() and not ln.upper().startswith("WEBVTT"):
                text_lines.append(ln)
        if not ts_line or not text_lines:
            continue
        match = _VTT_TS.search(ts_line)
        if not match:
            continue
        start = _ts_to_seconds(match.group(1), match.group(2), match.group(3), match.group(4))
        end = _ts_to_seconds(match.group(5), match.group(6), match.group(7), match.group(8))
        text = clean_caption_text(" ".join(text_lines))
        if text:
            segments.append(CaptionSegment(start=start, end=end, text=text))
    return normalize_caption_stream(segments)


def parse_json3(content: str) -> list[CaptionSegment]:
    data = json.loads(content)
    segments: list[CaptionSegment] = []
    for event in data.get("events", []):
        segs = event.get("segs") or []
        text = clean_caption_text("".join(part.get("utf8", "") for part in segs).replace("\n", " "))
        if not text:
            continue
        start_ms = event.get("tStartMs", 0)
        dur_ms = event.get("dDurationMs", 0)
        start = start_ms / 1000.0
        end = (start_ms + dur_ms) / 1000.0
        segments.append(CaptionSegment(start=start, end=end, text=text))
    return normalize_caption_stream(segments)


def _pick_caption_files(directory: Path, preferred_langs: list[str]) -> tuple[Optional[Path], Optional[str]]:
    candidates = list(directory.glob("*.vtt")) + list(directory.glob("*.json3")) + list(directory.glob("*.srt"))
    if not candidates:
        return None, None
    for lang in preferred_langs:
        for path in candidates:
            name = path.name.lower()
            if f".{lang}." in name or name.endswith(f".{lang}.vtt") or name.endswith(f".{lang}.json3"):
                return path, lang
    return candidates[0], None


def _load_captions(path: Path) -> list[CaptionSegment]:
    content = path.read_text(encoding="utf-8", errors="ignore")
    suffix = path.suffix.lower()
    if suffix == ".json3":
        return parse_json3(content)
    if suffix in {".vtt", ".srt"}:
        return parse_vtt(content)
    return []


def load_local_captions(directory: Path, language: str = "pl") -> tuple[list[CaptionSegment], Optional[str]]:
    caption_path, caption_lang = _pick_caption_files(directory, [language, f"{language}-PL", "en"])
    if caption_path is None:
        return [], None
    return _load_captions(caption_path), caption_lang


def _retry_ytdlp(
    fn: Callable[[], T],
    *,
    max_retries: int,
    backoff_seconds: float,
) -> T:
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - yt-dlp raises many types
            last_exc = exc
            if attempt >= max_retries - 1:
                break
            time.sleep(backoff_seconds * (2**attempt))
    assert last_exc is not None
    raise last_exc


def _download_with_retry(url: str, ydl_opts: dict[str, Any]) -> dict[str, Any]:
    from app.config import get_settings

    settings = get_settings()

    def _run() -> dict[str, Any]:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=True)

    return _retry_ytdlp(
        _run,
        max_retries=max(1, settings.ytdlp_max_retries),
        backoff_seconds=max(0.5, settings.ytdlp_retry_backoff_seconds),
    )


def _base_ydl_opts() -> dict[str, Any]:
    from app.config import get_settings

    settings = get_settings()
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        # A watch URL containing list= must still resolve to exactly one video.
        "noplaylist": True,
        # The provider runs as a private Compose service and supplies YouTube's
        # proof-of-origin tokens without account cookies.
        "extractor_args": {
            "youtubepot-bgutilhttp": {"base_url": ["http://pot-provider:4416"]},
        },
    }
    cookies = settings.ytdlp_cookies.strip()
    if cookies:
        opts["cookiefile"] = cookies
    proxy = settings.ytdlp_proxy.strip()
    if proxy:
        opts["proxy"] = proxy
    return opts


def _download_captions_best_effort(url: str, output_dir: Path, language: str) -> None:
    """Caption download is optional; HTTP 429 / missing tracks must not fail ingest."""
    outtmpl = str(output_dir / "%(id)s.%(ext)s")
    ydl_opts: dict[str, Any] = {
        **_base_ydl_opts(),
        "outtmpl": outtmpl,
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": [language, f"{language}-PL"],
        "subtitlesformat": "vtt/best",
        "ignoreerrors": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception:
        return


def ingest_youtube(
    url: str,
    output_dir: Path,
    language: str = "pl",
) -> YouTubeIngestResult:
    from app.config import get_settings

    settings = get_settings()
    output_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(output_dir / "%(id)s.%(ext)s")

    captions: list[CaptionSegment] = []
    caption_lang: Optional[str] = None
    info: dict[str, Any]

    if settings.captions_first:
        # Metadata + captions first; skip audio download if captions are usable.
        meta_opts = {**_base_ydl_opts(), "skip_download": True, "quiet": True}
        info = _download_with_retry(url, meta_opts)
        _download_captions_best_effort(url, output_dir, language)
        caption_path, caption_lang = _pick_caption_files(
            output_dir, [language, f"{language}-PL", "en"]
        )
        if caption_path is not None:
            captions = _load_captions(caption_path)
        if captions:
            video_id = info.get("id") or "unknown"
            return YouTubeIngestResult(
                title=info.get("title") or video_id,
                url=info.get("webpage_url") or url,
                video_id=video_id,
                duration_seconds=float(info["duration"]) if info.get("duration") is not None else None,
                audio_path=None,
                captions=captions,
                caption_lang=caption_lang,
            )

    # Audio download — do not couple media download to subtitle fetch failures.
    ydl_opts: dict[str, Any] = {
        **_base_ydl_opts(),
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "writesubtitles": False,
        "writeautomaticsub": False,
        "skip_download": False,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128",
            }
        ],
    }

    info = _download_with_retry(url, ydl_opts)

    video_id = info.get("id") or "unknown"
    title = info.get("title") or video_id
    duration = info.get("duration")
    webpage_url = info.get("webpage_url") or url

    audio_path = output_dir / f"{video_id}.mp3"
    if not audio_path.exists():
        matches = sorted(output_dir.glob(f"{video_id}.*"))
        audio_candidates = [p for p in matches if p.suffix.lower() in {".mp3", ".m4a", ".webm", ".opus", ".wav"}]
        audio_path = audio_candidates[0] if audio_candidates else None

    if not captions:
        _download_captions_best_effort(url, output_dir, language)
        caption_path, caption_lang = _pick_caption_files(
            output_dir, [language, f"{language}-PL", "en"]
        )
        if caption_path is not None:
            captions = _load_captions(caption_path)

    return YouTubeIngestResult(
        title=title,
        url=webpage_url,
        video_id=video_id,
        duration_seconds=float(duration) if duration is not None else None,
        audio_path=audio_path,
        captions=captions,
        caption_lang=caption_lang,
    )


def list_subs(url: str) -> dict[str, Any]:
    ydl_opts = {**_base_ydl_opts(), "skip_download": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "duration": info.get("duration"),
        "subtitles": list((info.get("subtitles") or {}).keys()),
        "automatic_captions": list((info.get("automatic_captions") or {}).keys()),
    }

def expand_youtube_urls(urls: list[str], max_videos: int = 50) -> list[str]:
    """Expand playlist/list= URLs into watch URLs; keep plain video URLs as-is."""
    from urllib.parse import parse_qs, urlparse

    expanded: list[str] = []
    seen: set[str] = set()

    def add(url: str) -> None:
        key = url.strip()
        if not key or key in seen:
            return
        seen.add(key)
        expanded.append(key)

    for raw in urls:
        url = (raw or "").strip()
        if not url:
            continue
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        is_playlist = "list" in qs or "playlist" in parsed.path
        if not is_playlist:
            add(url)
            continue
        try:
            import yt_dlp
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("yt-dlp is required to expand playlists") from exc
        opts = {
            "quiet": True,
            "skip_download": True,
            "extract_flat": True,
            "noplaylist": False,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        entries = info.get("entries") or []
        if not entries and info.get("id"):
            add(f"https://www.youtube.com/watch?v={info['id']}")
            continue
        for entry in entries:
            if len(expanded) >= max_videos:
                break
            if not entry:
                continue
            vid = entry.get("id") or entry.get("url")
            if not vid:
                continue
            if isinstance(vid, str) and vid.startswith("http"):
                add(vid)
            else:
                add(f"https://www.youtube.com/watch?v={vid}")
        if len(expanded) >= max_videos:
            break
    return expanded[:max_videos]
