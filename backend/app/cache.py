from __future__ import annotations

import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Segment, Source, Summary

_YT_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{6,})"
)


def extract_youtube_video_id(url: str) -> Optional[str]:
    if not url:
        return None
    match = _YT_ID_RE.search(url)
    return match.group(1) if match else None


def canonical_youtube_video_url(url: str) -> str:
    """Return a watch URL for one video, dropping playlist/tracking parameters."""
    video_id = extract_youtube_video_id(url)
    if not video_id:
        return url
    return f"https://www.youtube.com/watch?v={video_id}"


def find_cached_source(db: Session, video_id: str, user_id: str) -> Optional[Source]:
    return db.scalar(
        select(Source)
        .where(
            Source.video_id == video_id,
            Source.user_id == user_id,
            Source.status == "ready",
        )
        .options(selectinload(Source.segments), selectinload(Source.summaries))
        .order_by(Source.id.desc())
    )


def clone_source_from_cache(db: Session, target: Source, cached: Source) -> None:
    target.title = cached.title
    target.duration_seconds = cached.duration_seconds
    target.transcript_method = cached.transcript_method
    target.video_id = cached.video_id
    target.file_path = cached.file_path
    target.error = None
    target.error_code = None
    target.error_hint = None

    target.segments.clear()
    target.summaries.clear()
    db.flush()

    for idx, seg in enumerate(sorted(cached.segments, key=lambda s: s.ord)):
        db.add(
            Segment(
                source_id=target.id,
                start=seg.start,
                end=seg.end,
                text=seg.text,
                ord=idx,
            )
        )
    for summary in cached.summaries:
        db.add(
            Summary(
                source_id=target.id,
                kind=summary.kind,
                content=summary.content,
            )
        )
    target.status = "ready"
