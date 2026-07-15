from datetime import datetime, timedelta, timezone

from app.config import Settings
from app.limits import check_duration_limit, enforce_daily_source_limit
from app.models import Source


def test_check_duration_limit_raises():
    settings = Settings(max_video_duration_seconds=60)
    try:
        check_duration_limit(120.0, settings)
        raised = False
    except Exception as exc:
        raised = True
        assert "maximum duration" in str(exc)
    assert raised


def test_daily_source_limit(client, db_session, monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("DAILY_SOURCE_LIMIT", "1")
    get_settings.cache_clear()

    db_session.add(
        Source(
            user_id="anonymous",
            source_type="text",
            title="Old",
            status="ready",
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
    )
    db_session.commit()

    res = client.post(
        "/api/sources/text",
        json={"title": "New", "text": "Krótki tekst.", "auto_summarize": False},
    )
    assert res.status_code == 429
    get_settings.cache_clear()
