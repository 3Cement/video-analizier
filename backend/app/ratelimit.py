from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import RateLimitEvent


def enforce_rate_limit(
    db: Session, key: str, *, limit: int, window_seconds: int, detail: str
) -> None:
    """Persist rate-limit events so limits survive restarts and work across API replicas."""
    if limit <= 0:
        return
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    count = db.scalar(
        select(func.count()).select_from(RateLimitEvent).where(
            RateLimitEvent.bucket == key, RateLimitEvent.created_at >= cutoff
        )
    ) or 0
    if count >= limit:
        raise HTTPException(status_code=429, detail=detail)
    db.add(RateLimitEvent(bucket=key))
    db.commit()


def clear_rate_limits(db: Session | None = None) -> None:
    if db is not None:
        db.execute(delete(RateLimitEvent))
        db.commit()
