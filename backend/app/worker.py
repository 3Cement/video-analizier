from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select, update

from app.config import get_settings
from app.db import get_session
from app.models import Source
from app.pipeline import (
    process_article_source,
    process_podcast_source,
    process_upload_source,
    process_youtube_source,
)

logger = logging.getLogger(__name__)


def reclaim_stale_jobs(db) -> int:
    settings = get_settings()
    stale_before = datetime.now(timezone.utc) - timedelta(seconds=max(60, settings.job_stale_seconds))
    result = db.execute(
        update(Source)
        .where(
            Source.status.in_(("downloading", "transcribing", "summarizing")),
            Source.claimed_at.is_not(None),
            Source.claimed_at < stale_before,
        )
        .values(
            status="pending",
            claimed_at=None,
            progress_message="requeued_stale",
        )
    )
    db.commit()
    return int(result.rowcount or 0)


def claim_next_pending(db) -> Source | None:
    now = datetime.now(timezone.utc)
    source = db.scalar(
        select(Source)
        .where(
            Source.status == "pending",
            or_(Source.next_run_at.is_(None), Source.next_run_at <= now),
        )
        .order_by(Source.id.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if source is None:
        return None
    source.status = "downloading"
    source.claimed_at = now
    source.attempts = int(source.attempts or 0) + 1
    source.progress_message = "claimed"
    db.commit()
    db.refresh(source)
    return source


def _dispatch(db, source: Source) -> None:
    if source.source_type == "youtube":
        process_youtube_source(db, source.id, auto_summarize=True)
        return
    if source.source_type == "article":
        process_article_source(db, source.id, auto_summarize=True)
        return
    if source.source_type == "podcast":
        process_podcast_source(db, source.id, auto_summarize=True)
        return
    if source.source_type in {"pdf", "audio", "audiobook", "book", "text", "document"}:
        process_upload_source(db, source.id, auto_summarize=True)
        return
    source.status = "failed"
    source.error = f"Unsupported source type: {source.source_type}"
    source.error_code = "processing_failed"
    source.error_hint = "This source type cannot be processed by the worker."
    db.commit()


def run_worker_once(db) -> bool:
    reclaim_stale_jobs(db)
    source = claim_next_pending(db)
    if source is None:
        return False
    started = time.monotonic()
    try:
        _dispatch(db, source)
        logger.info("job_complete job_id=%s user_id=%s source_type=%s duration_ms=%d",
                    source.id, source.user_id, source.source_type, int((time.monotonic() - started) * 1000))
    except Exception:
        db.rollback()
        failed = db.get(Source, source.id)
        logger.exception("job_failed job_id=%s user_id=%s source_type=%s duration_ms=%d error_code=%s",
                         source.id, source.user_id, source.source_type,
                         int((time.monotonic() - started) * 1000), getattr(failed, "error_code", "unknown"))
        raise
    return True


def preload_whisper() -> None:
    try:
        from app.asr.whisper import _get_model
        from app.config import get_settings

        _get_model(get_settings())
    except Exception:
        return


def run_worker_loop() -> None:
    settings = get_settings()
    settings.ensure_dirs()
    preload_whisper()
    poll = max(1.0, settings.worker_poll_seconds)

    while True:
        db = get_session()
        try:
            worked = run_worker_once(db)
            if not worked:
                time.sleep(poll)
        except Exception:
            db.rollback()
            time.sleep(poll)
        finally:
            db.close()


if __name__ == "__main__":
    run_worker_loop()
