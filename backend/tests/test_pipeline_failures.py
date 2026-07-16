from unittest.mock import patch

from app.models import Source
from app.pipeline import process_text_source, process_youtube_source


def test_youtube_pipeline_persists_classified_error(db_session):
    source = Source(
        source_type="youtube",
        title="Fail video",
        url="https://www.youtube.com/watch?v=abcdefghijk",
        status="pending",
        user_id="anonymous",
    )
    db_session.add(source)
    db_session.commit()

    with patch(
        "app.pipeline.ingest_youtube",
        side_effect=RuntimeError("Sign in to confirm you're not a bot"),
    ):
        try:
            process_youtube_source(db_session, source.id, auto_summarize=False)
            raised = False
        except RuntimeError:
            raised = True

    assert raised
    db_session.refresh(source)
    assert source.status in {"failed", "pending"}
    assert source.error_code
    if source.status == "pending":
        assert source.next_run_at is not None
    assert source.error_code == "youtube_bot_check"
    assert source.error_hint
    assert "bot" in (source.error or "").lower()


def test_text_pipeline_ready(db_session, monkeypatch, tmp_path):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("MEDIA_DIR", str(tmp_path / "media"))
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("CURSOR_API_KEY", "")
    get_settings.cache_clear()

    source = Source(source_type="text", title="Note", status="pending", user_id="anonymous")
    db_session.add(source)
    db_session.commit()

    process_text_source(
        db_session,
        source.id,
        text="Najpierw podsmaż cebulę. Potem dodaj jajka.",
        auto_summarize=True,
    )
    db_session.refresh(source)
    assert source.status == "ready"
    assert source.transcript_method == "text"
    assert len(source.segments) >= 1
    assert source.summaries
    get_settings.cache_clear()
