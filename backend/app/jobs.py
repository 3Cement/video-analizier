from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.db import get_session

_executor: ThreadPoolExecutor | None = None


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        from app.config import get_settings

        settings = get_settings()
        _executor = ThreadPoolExecutor(
            max_workers=max(1, settings.job_max_workers),
            thread_name_prefix="va-job",
        )
    return _executor


def run_in_background(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    from app.config import get_settings

    settings = get_settings()
    if settings.worker_mode:
        return

    def _target() -> None:
        db = get_session()
        try:
            fn(db, *args, **kwargs)
        finally:
            db.close()

    _get_executor().submit(_target)
