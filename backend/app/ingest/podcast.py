from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx

_UA = "Mozilla/5.0 (compatible; video-analizier/0.3; podcast-ingest)"
_AUDIO_EXT = {".mp3", ".m4a", ".m4b", ".ogg", ".opus", ".wav", ".flac", ".aac", ".mp4"}


@dataclass
class PodcastEpisode:
    title: str
    audio_url: str
    page_url: Optional[str] = None
    duration_hint: Optional[float] = None
    show_title: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[str] = None
    guid: Optional[str] = None


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _text(el: Optional[ET.Element]) -> str:
    if el is None:
        return ""
    if el.text:
        return re.sub(r"\s+", " ", el.text).strip()
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def _parse_duration(raw: str) -> Optional[float]:
    raw = raw.strip()
    if raw.isdigit():
        return float(raw)
    parts = raw.split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return None
    if len(nums) == 3:
        return float(nums[0] * 3600 + nums[1] * 60 + nums[2])
    if len(nums) == 2:
        return float(nums[0] * 60 + nums[1])
    return None


def parse_rss(feed_xml: str, max_episodes: int = 5) -> list[PodcastEpisode]:
    root = ET.fromstring(feed_xml)
    show_title = ""
    show_author = ""
    for el in root.iter():
        name = _strip_ns(el.tag).lower()
        if name == "channel":
            for child in list(el):
                cname = _strip_ns(child.tag).lower()
                if cname == "title" and not show_title:
                    show_title = _text(child)
                elif cname in {"author", "name"} and not show_author:
                    show_author = _text(child)
            break

    items: list[ET.Element] = []
    for el in root.iter():
        if _strip_ns(el.tag) == "item":
            items.append(el)

    episodes: list[PodcastEpisode] = []
    for item in items:
        title = ""
        page_url = None
        audio_url = None
        duration_hint = None
        description = None
        author = show_author or None
        published_at = None
        guid = None
        for child in list(item):
            name = _strip_ns(child.tag).lower()
            if name == "title" and not title:
                title = _text(child)
            elif name == "link" and not page_url:
                page_url = _text(child) or child.get("href")
            elif name == "enclosure":
                enc_url = child.get("url") or ""
                enc_type = (child.get("type") or "").lower()
                if enc_url and ("audio" in enc_type or Path(urlparse(enc_url).path).suffix.lower() in _AUDIO_EXT):
                    audio_url = enc_url
            elif name == "duration":
                raw = _text(child)
                duration_hint = _parse_duration(raw) if raw else duration_hint
            elif name in {"description", "summary"} and not description:
                description = _text(child)[:2000] or None
            elif name in {"author", "creator"} and not author:
                author = _text(child) or author
            elif name in {"pubdate", "date"} and not published_at:
                published_at = _text(child) or None
            elif name == "guid" and not guid:
                guid = _text(child) or child.get("isPermaLink")
        if not audio_url:
            continue
        episodes.append(
            PodcastEpisode(
                title=title or "Podcast episode",
                audio_url=audio_url,
                page_url=page_url,
                duration_hint=duration_hint,
                show_title=show_title or None,
                description=description,
                author=author,
                published_at=published_at,
                guid=guid,
            )
        )
        if len(episodes) >= max_episodes:
            break
    return episodes


def fetch_rss_episodes(feed_url: str, max_episodes: int = 5, timeout: float = 45.0) -> list[PodcastEpisode]:
    with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": _UA}) as client:
        response = client.get(feed_url)
        response.raise_for_status()
        return parse_rss(response.text, max_episodes=max_episodes)


def resolve_episode_audio(url: str, timeout: float = 45.0) -> PodcastEpisode:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in _AUDIO_EXT:
        name = Path(urlparse(url).path).name or "episode"
        return PodcastEpisode(title=name, audio_url=url, page_url=url)

    with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": _UA}) as client:
        response = client.get(url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        body = response.text

    if "xml" in content_type or body.lstrip().startswith("<?xml") or "<rss" in body[:400].lower():
        episodes = parse_rss(body, max_episodes=1)
        if not episodes:
            raise RuntimeError("RSS feed has no audio tags")
        return episodes[0]

    audio_match = re.search(
        r'(?:og:audio|audio["\']?\s+src|href)=["\']([^"\']+\.(?:mp3|m4a|m4b|ogg|opus|wav|flac))["\']',
        body,
        flags=re.I,
    )
    title_match = re.search(r"<title>(.*?)</title>", body, flags=re.I | re.S)
    title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else "Podcast episode"
    if audio_match:
        return PodcastEpisode(title=title, audio_url=audio_match.group(1), page_url=url)
    raise RuntimeError("Could not resolve podcast audio URL from page")


def download_audio(audio_url: str, dest: Path, timeout: float = 180.0) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": _UA}) as client:
        with client.stream("GET", audio_url) as response:
            response.raise_for_status()
            with dest.open("wb") as out:
                for chunk in response.iter_bytes():
                    out.write(chunk)
    return dest
