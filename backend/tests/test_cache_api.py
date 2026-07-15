from unittest.mock import patch

from app.models import Segment, Source, Summary


def test_youtube_cache_hit_skips_background_job(client, db_session):
    cached = Source(
        user_id="anonymous",
        source_type="youtube",
        title="Cached title",
        url="https://www.youtube.com/watch?v=tPsVjYR0tGY",
        video_id="tPsVjYR0tGY",
        status="ready",
        transcript_method="captions",
    )
    db_session.add(cached)
    db_session.flush()
    db_session.add(Segment(source_id=cached.id, start=0.0, end=1.0, text="Hello", ord=0))
    db_session.add(Summary(source_id=cached.id, kind="briefing", content="Brief"))
    db_session.commit()

    with patch("app.api.routes.run_in_background") as bg:
        res = client.post(
            "/api/sources/youtube",
            json={"url": "https://www.youtube.com/watch?v=tPsVjYR0tGY", "auto_summarize": False},
        )
        assert res.status_code == 200
        assert bg.called is False

    body = res.json()
    assert body["status"] == "ready"
    assert body["title"] == "Cached title"
    assert body["segment_count"] == 1
