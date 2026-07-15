from __future__ import annotations

from app.asr.whisper import AsrSegment
from app.ingest.captions import CaptionSegment, clean_caption_text, normalize_caption_stream


def normalize_asr_segments(segments: list[AsrSegment]) -> list[AsrSegment]:
    """Apply the same caption cleanup/merge heuristics to Whisper output."""
    caption_like = [
        CaptionSegment(start=seg.start, end=seg.end, text=clean_caption_text(seg.text))
        for seg in segments
        if seg.text.strip()
    ]
    normalized = normalize_caption_stream(caption_like)
    return [
        AsrSegment(start=item.start, end=item.end, text=item.text)
        for item in normalized
    ]
