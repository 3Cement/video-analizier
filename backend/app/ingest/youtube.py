from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yt_dlp


@dataclass
class CaptionSegment:
    start: float
    end: float
    text: str


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
_TAG = re.compile(r"<[^>]+>")


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
                text_lines.append(_TAG.sub("", ln))
        if not ts_line or not text_lines:
            continue
        match = _VTT_TS.search(ts_line)
        if not match:
            continue
        start = _ts_to_seconds(match.group(1), match.group(2), match.group(3), match.group(4))
        end = _ts_to_seconds(match.group(5), match.group(6), match.group(7), match.group(8))
        text = " ".join(text_lines).strip()
        if text:
            segments.append(CaptionSegment(start=start, end=end, text=text))
    return _dedupe_captions(segments)


def parse_json3(content: str) -> list[CaptionSegment]:
    data = json.loads(content)
    segments: list[CaptionSegment] = []
    for event in data.get("events", []):
        segs = event.get("segs") or []
        text = "".join(part.get("utf8", "") for part in segs).replace("\n", " ").strip()
        if not text or text == "\n":
            continue
        start_ms = event.get("tStartMs", 0)
        dur_ms = event.get("dDurationMs", 0)
        start = start_ms / 1000.0
        end = (start_ms + dur_ms) / 1000.0
        segments.append(CaptionSegment(start=start, end=end, text=text))
    return _dedupe_captions(segments)


def _dedupe_captions(segments: list[CaptionSegment]) -> list[CaptionSegment]:
    if not segments:
        return []
    out: list[CaptionSegment] = [segments[0]]
    for seg in segments[1:]:
        prev = out[-1]
        if seg.text == prev.text and abs(seg.start - prev.start) < 0.35:
            continue
        if seg.text.startswith(prev.text) and seg.start <= prev.end + 0.5:
            out[-1] = CaptionSegment(start=prev.start, end=max(prev.end, seg.end), text=seg.text)
            continue
        out.append(seg)
    return out


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


def _base_ydl_opts() -> dict[str, Any]:
    from app.config import get_settings

    settings = get_settings()
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        # android_vr often works on restricted/datacenter IPs for public videos
        "extractor_args": {"youtube": {"player_client": ["android_vr", "android", "web"]}},
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
    output_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(output_dir / "%(id)s.%(ext)s")

    # Audio first — do not couple media download to subtitle fetch failures.
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

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    video_id = info.get("id") or "unknown"
    title = info.get("title") or video_id
    duration = info.get("duration")
    webpage_url = info.get("webpage_url") or url

    audio_path = output_dir / f"{video_id}.mp3"
    if not audio_path.exists():
        matches = sorted(output_dir.glob(f"{video_id}.*"))
        audio_candidates = [p for p in matches if p.suffix.lower() in {".mp3", ".m4a", ".webm", ".opus", ".wav"}]
        audio_path = audio_candidates[0] if audio_candidates else None

    _download_captions_best_effort(url, output_dir, language)

    caption_path, caption_lang = _pick_caption_files(output_dir, [language, f"{language}-PL", "en"])
    captions: list[CaptionSegment] = []
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