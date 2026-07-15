from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Source


class DurationLimitError(Exception):
    pass


def check_duration_limit(
    duration_seconds: float | None,
    settings: Settings,
    *,
    kind: str = "video",
) -> None:
    if duration_seconds is None:
        return
    if kind == "audio":
        max_seconds = settings.max_audio_duration_seconds
        label = "Audio"
    else:
        max_seconds = settings.max_video_duration_seconds
        label = "Video"
    if max_seconds <= 0:
        return
    if duration_seconds > max_seconds:
        minutes = int(max_seconds // 60)
        raise DurationLimitError(f"{label} exceeds maximum duration ({minutes} minutes).")


def _daily_count(db: Session, user_id: str, since, source_type: str | None = None) -> int:
    stmt = (
        select(func.count())
        .select_from(Source)
        .where(Source.user_id == user_id, Source.created_at >= since)
    )
    if source_type:
        stmt = stmt.where(Source.source_type == source_type)
    count = db.scalar(stmt)
    return int(count or 0)


def enforce_daily_source_limit(
    db: Session,
    user_id: str,
    settings: Settings,
    *,
    source_type: str | None = None,
) -> None:
    since = datetime.now(timezone.utc) - timedelta(days=1)
    global_limit = settings.daily_source_limit
    if global_limit > 0:
        used = _daily_count(db, user_id, since)
        if used >= global_limit:
            raise HTTPException(
                status_code=429,
                detail=f"Daily source limit reached ({global_limit} per 24h).",
            )

    type_limits = {
        "youtube": settings.daily_youtube_limit,
        "podcast": settings.daily_audio_limit,
        "audio": settings.daily_audio_limit,
        "audiobook": settings.daily_audio_limit,
        "article": settings.daily_article_limit,
        "book": settings.daily_article_limit,
        "pdf": settings.daily_article_limit,
        "text": settings.daily_article_limit,
    }
    if source_type and source_type in type_limits:
        limit = type_limits[source_type]
        if limit > 0:
            used = _daily_count(db, user_id, since, source_type=source_type)
            if used >= limit:
                raise HTTPException(
                    status_code=429,
                    detail=f"Daily {source_type} limit reached ({limit} per 24h).",
                )


def enforce_duration_limit(
    duration_seconds: float | None,
    settings: Settings,
    *,
    kind: str = "video",
) -> None:
    try:
        check_duration_limit(duration_seconds, settings, kind=kind)
    except DurationLimitError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
