from unittest.mock import patch

import pytest

from app.ingest.youtube import _retry_ytdlp


def test_retry_succeeds_after_transient_failures():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("temporary")
        return {"ok": True}

    with patch("app.ingest.youtube.time.sleep") as sleep_mock:
        out = _retry_ytdlp(flaky, max_retries=3, backoff_seconds=1.0)

    assert out == {"ok": True}
    assert calls["n"] == 3
    assert sleep_mock.call_count == 2
    sleep_mock.assert_any_call(1.0)
    sleep_mock.assert_any_call(2.0)


def test_retry_raises_after_exhaustion():
    def always_fail():
        raise RuntimeError("permanent")

    with patch("app.ingest.youtube.time.sleep"):
        with pytest.raises(RuntimeError, match="permanent"):
            _retry_ytdlp(always_fail, max_retries=2, backoff_seconds=0.5)
