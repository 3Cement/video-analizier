from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException


_buckets: dict[str, deque[float]] = defaultdict(deque)


def enforce_rate_limit(key: str, *, limit: int, window_seconds: int, detail: str) -> None:
    if limit <= 0:
        return
    now = time.time()
    bucket = _buckets[key]
    while bucket and bucket[0] <= now - window_seconds:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(status_code=429, detail=detail)
    bucket.append(now)


def clear_rate_limits() -> None:
    _buckets.clear()
