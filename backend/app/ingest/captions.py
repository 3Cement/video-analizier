from __future__ import annotations

import html
import re
from dataclasses import dataclass


@dataclass
class CaptionSegment:
    start: float
    end: float
    text: str


_TAG = re.compile(r"<[^>]+>")
_MUSIC = re.compile(r"(?:>>|&gt;&gt;|\u266a|\u266b)?\s*\[(?:muzyka|music|Applause|apka?uza)\]", re.I)
_NOISE = re.compile(r"(?:>>|&gt;&gt;)+")
_MULTI_SPACE = re.compile(r"\s+")


def clean_caption_text(text: str) -> str:
    value = html.unescape(text or "")
    value = _TAG.sub("", value)
    value = _MUSIC.sub(" ", value)
    value = _NOISE.sub(" ", value)
    value = value.replace("\xa0", " ")
    value = _MULTI_SPACE.sub(" ", value).strip(" -\t")
    return value


def _token_overlap_prefix(prev: list[str], curr: list[str]) -> int:
    """Longest prefix of curr that is a suffix of prev (rolling caption effect)."""
    max_k = min(len(prev), len(curr))
    for k in range(max_k, 0, -1):
        if prev[-k:] == curr[:k]:
            return k
    return 0


def normalize_caption_stream(segments: list[CaptionSegment]) -> list[CaptionSegment]:
    """Turn overlapping YouTube auto-captions into clearer non-rolling sentences."""
    cleaned: list[CaptionSegment] = []
    for seg in segments:
        text = clean_caption_text(seg.text)
        if not text:
            continue
        cleaned.append(CaptionSegment(start=seg.start, end=seg.end, text=text))

    if not cleaned:
        return []

    deltas: list[CaptionSegment] = []
    prev_tokens: list[str] = []
    for seg in cleaned:
        tokens = seg.text.split()
        if not tokens:
            continue
        overlap = _token_overlap_prefix(prev_tokens, tokens)
        new_tokens = tokens[overlap:] if overlap else tokens
        if not new_tokens:
            # pure repeat / extension already spoken — extend previous end if close
            if deltas and abs(seg.start - deltas[-1].end) < 2.5:
                deltas[-1] = CaptionSegment(
                    start=deltas[-1].start,
                    end=max(deltas[-1].end, seg.end),
                    text=deltas[-1].text,
                )
            prev_tokens = tokens
            continue
        deltas.append(CaptionSegment(start=seg.start, end=seg.end, text=" ".join(new_tokens)))
        prev_tokens = tokens

    # Merge only short/close fragments; keep complete sentences separate.
    merged: list[CaptionSegment] = []
    buf: list[str] = []
    buf_start: float | None = None
    buf_end = 0.0

    def flush() -> None:
        nonlocal buf, buf_start, buf_end
        if buf and buf_start is not None:
            merged.append(CaptionSegment(start=buf_start, end=buf_end, text=" ".join(buf)))
        buf = []
        buf_start = None
        buf_end = 0.0

    for seg in deltas:
        if buf_start is None:
            buf_start = seg.start
            buf = [seg.text]
            buf_end = seg.end
            continue

        gap = seg.start - buf_end
        prev_len = len(buf[-1])
        should_merge = (gap <= 0.9) or (len(seg.text) < 42 and prev_len < 70)
        if not should_merge:
            flush()
            buf_start = seg.start
            buf = [seg.text]
            buf_end = seg.end
            continue

        buf.append(seg.text)
        buf_end = seg.end
        joined = " ".join(buf)
        if len(joined) >= 140 or (buf_end - buf_start) >= 14.0:
            flush()

    flush()
    return merged
