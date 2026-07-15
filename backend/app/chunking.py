from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TextChunk:
    start: float
    end: float
    text: str


def format_timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def chunk_segments(
    segments: list[tuple[float, float, str]],
    max_chars: int = 2800,
) -> list[TextChunk]:
    """Merge timestamped segments into larger context windows."""
    chunks: list[TextChunk] = []
    buf_parts: list[str] = []
    buf_start: float | None = None
    buf_end: float = 0.0
    buf_len = 0

    def flush() -> None:
        nonlocal buf_parts, buf_start, buf_end, buf_len
        if not buf_parts or buf_start is None:
            return
        chunks.append(
            TextChunk(start=buf_start, end=buf_end, text=" ".join(buf_parts).strip())
        )
        buf_parts = []
        buf_start = None
        buf_end = 0.0
        buf_len = 0

    for start, end, text in segments:
        clean = (text or "").strip()
        if not clean:
            continue
        piece = f"[{format_timestamp(start)}] {clean}"
        if buf_parts and buf_len + len(piece) + 1 > max_chars:
            flush()
        if buf_start is None:
            buf_start = start
        buf_parts.append(piece)
        buf_end = end
        buf_len += len(piece) + 1

    flush()
    return chunks


def segments_to_transcript(
    segments: list[tuple[float, float, str]],
    with_timestamps: bool = True,
) -> str:
    lines: list[str] = []
    for start, end, text in segments:
        clean = (text or "").strip()
        if not clean:
            continue
        if with_timestamps:
            lines.append(f"[{format_timestamp(start)}] {clean}")
        else:
            lines.append(clean)
    return "\n".join(lines)
