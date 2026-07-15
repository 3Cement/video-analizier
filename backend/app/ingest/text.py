from __future__ import annotations

from pathlib import Path


def load_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def text_to_segments(text: str, chars_per_segment: int = 700) -> list[tuple[float, float, str]]:
    words = text.split()
    if not words:
        return []
    segments: list[tuple[float, float, str]] = []
    buf: list[str] = []
    idx = 0
    fake_t = 0.0
    for word in words:
        buf.append(word)
        if sum(len(w) + 1 for w in buf) >= chars_per_segment:
            chunk = " ".join(buf)
            start = fake_t
            end = fake_t + max(3.0, len(chunk) / 14.0)
            segments.append((start, end, chunk))
            fake_t = end
            buf = []
            idx += 1
    if buf:
        chunk = " ".join(buf)
        start = fake_t
        end = fake_t + max(3.0, len(chunk) / 14.0)
        segments.append((start, end, chunk))
    return segments