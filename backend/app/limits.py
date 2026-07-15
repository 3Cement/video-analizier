from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Source


class DurationLimitError(Exception):
    pass


def check_duration_limit(duration_seconds: float | None, settings: Settings) -> None:
    max_seconds = settings.max_video_duration_seconds
    if max_seconds <= 0 or duration_seconds is None:
        return
    if duration_seconds > max_seconds:
        minutes = int(max_seconds // 60)
        raise DurationLimitError(f"Video exceeds maximum duration ({minutes} minutes).")


def enforce_daily_source_limit(db: Session, user_id: str, settings: Settings) -> None:
    limit = settings.daily_source_limit
    if limit <= 0:
        return
    since = datetime.now(timezone.utc) - timedelta(days=1)
    count = db.scalar(
        select(func.count())
        .select_from(Source)
        .where(Source.user_id == user_id, Source.created_at >= since)
    )
    if count is not None and count >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Daily source limit reached ({limit} per 24h).",
        )


def enforce_duration_limit(duration_seconds: float | None, settings: Settings) -> None:
    try:
        check_duration_limit(duration_seconds, settings)
    except DurationLimitError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
