from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from app.db import get_session


def run_in_background(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    def _target() -> None:
        db = get_session()
        try:
            fn(db, *args, **kwargs)
        finally:
            db.close()

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()