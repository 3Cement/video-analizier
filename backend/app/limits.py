from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.chunking import chunk_segments
from app.models import Source, UsageEvent


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


def _usage_count(db: Session, event_type: str, *, user_id: str | None = None) -> int:
    since = datetime.now(timezone.utc) - timedelta(days=1)
    stmt = select(func.coalesce(func.sum(UsageEvent.units), 0)).where(
        UsageEvent.event_type == event_type, UsageEvent.created_at >= since
    )
    if user_id is not None:
        stmt = stmt.where(UsageEvent.user_id == user_id)
    return int(db.scalar(stmt) or 0)


def enforce_question_limit(db: Session, user_id: str, settings: Settings) -> None:
    used = _usage_count(db, "question", user_id=user_id)
    if settings.daily_question_limit > 0 and used >= settings.daily_question_limit:
        raise HTTPException(status_code=429, detail="Daily question limit reached")


def record_usage(db: Session, event_type: str, *, user_id: str | None, source_id: int | None = None, units: int = 1) -> None:
    db.add(UsageEvent(user_id=user_id, event_type=event_type, source_id=source_id, units=units))
    db.commit()


def estimate_summary_calls(segments: list[tuple[float, float, str]], settings: Settings) -> int:
    chunks = chunk_segments(segments, max_chars=2800)
    count = min(len(chunks), max(1, settings.max_summary_chunks))
    return 1 if count <= 1 else count + 1


def llm_allowed(db: Session, settings: Settings, required_calls: int = 1) -> bool:
    return settings.global_daily_llm_limit <= 0 or _usage_count(db, "llm_call") + required_calls <= settings.global_daily_llm_limit


def quota_snapshot(db: Session, user_id: str, settings: Settings) -> dict[str, tuple[int, int]]:
    since = datetime.now(timezone.utc) - timedelta(days=1)
    sources = int(db.scalar(select(func.count()).select_from(Source).where(Source.user_id == user_id, Source.created_at >= since)) or 0)
    questions = _usage_count(db, "question", user_id=user_id)
    global_llm = _usage_count(db, "llm_call")
    return {"sources": (sources, settings.daily_source_limit), "questions": (questions, settings.daily_question_limit), "global_llm": (global_llm, settings.global_daily_llm_limit)}


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
