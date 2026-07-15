from __future__ import annotations

import time

from sqlalchemy import select

from app.config import get_settings
from app.db import get_session, init_db
from app.models import Source
from app.pipeline import process_text_source, process_upload_source, process_youtube_source


def _dispatch(db, source: Source) -> None:
    if source.source_type == "youtube":
        process_youtube_source(db, source.id, auto_summarize=True)
    elif source.source_type == "text":
        raise RuntimeError("Text sources require inline content and cannot be replayed by worker")
    elif source.source_type in {"pdf", "audio", "text"}:
        process_upload_source(db, source.id, auto_summarize=True)
    else:
        raise RuntimeError(f"Unsupported source type: {source.source_type}")


def run_worker_loop() -> None:
    settings = get_settings()
    settings.ensure_dirs()
    init_db()
    poll = max(1.0, settings.worker_poll_seconds)

    while True:
        db = get_session()
        try:
            source = db.scalar(
                select(Source)
                .where(Source.status == "pending")
                .order_by(Source.id.asc())
                .limit(1)
            )
            if source is None:
                time.sleep(poll)
                continue
            _dispatch(db, source)
        except Exception:
            db.rollback()
        finally:
            db.close()


if __name__ == "__main__":
    run_worker_loop()
