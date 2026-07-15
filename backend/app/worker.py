from __future__ import annotations

import time

from sqlalchemy import select, update

from app.config import get_settings
from app.db import get_session, init_db
from app.models import Source
from app.pipeline import (
    process_article_source,
    process_podcast_source,
    process_upload_source,
    process_youtube_source,
)


def claim_next_pending(db) -> Source | None:
    source = db.scalar(
        select(Source)
        .where(Source.status == "pending")
        .order_by(Source.id.asc())
        .limit(1)
    )
    if source is None:
        return None
    result = db.execute(
        update(Source)
        .where(Source.id == source.id, Source.status == "pending")
        .values(status="downloading")
    )
    db.commit()
    if result.rowcount == 0:
        return None
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
    if source.source_type in {"pdf", "audio", "audiobook", "book", "text"}:
        process_upload_source(db, source.id, auto_summarize=True)
        return
    source.status = "failed"
    source.error = f"Unsupported source type: {source.source_type}"
    source.error_code = "processing_failed"
    source.error_hint = "This source type cannot be processed by the worker."
    db.commit()


def run_worker_once(db) -> bool:
    source = claim_next_pending(db)
    if source is None:
        return False
    _dispatch(db, source)
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
    init_db()
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
