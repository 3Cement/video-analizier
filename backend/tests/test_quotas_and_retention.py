from pathlib import Path
from unittest.mock import patch

from app.config import get_settings
from app.models import Segment, Source, UsageEvent
from app.pipeline import process_upload_source


def test_text_size_limit(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_text_bytes", 5)
    response = client.post("/api/sources/text", json={"title": "large", "text": "123456", "auto_summarize": False})
    assert response.status_code == 413


def test_upload_size_limit_removes_partial_source(client, db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_bytes", 4)
    response = client.post("/api/sources/upload", files={"file": ("large.txt", b"12345", "text/plain")})
    assert response.status_code == 413
    assert db_session.query(Source).filter(Source.title == "large.txt").count() == 0


def test_global_llm_fuse_uses_extractive_summary(client, db_session, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "global_daily_llm_limit", 1)
    monkeypatch.setattr(settings, "openai_api_key", "server-key")
    source = Source(user_id="anonymous", source_type="text", title="Fuse", status="ready")
    db_session.add(source)
    db_session.flush()
    db_session.add(Segment(source_id=source.id, start=0, end=1, text="To jest wystarczająco długi fragment źródłowy do lokalnego podsumowania.", ord=0))
    db_session.add(UsageEvent(user_id="another", event_type="llm_call", units=1))
    db_session.commit()
    with patch("app.llm.summarize.chat_completion") as completion:
        response = client.post(f"/api/sources/{source.id}/summarize", json={"kind": "briefing"})
    assert response.status_code == 200
    completion.assert_not_called()


def test_successful_audio_transcription_removes_heavy_media(db_session, monkeypatch):
    settings = get_settings()
    source = Source(user_id="anonymous", source_type="audio", title="Audio", status="pending")
    db_session.add(source)
    db_session.commit()
    work_dir = settings.media_dir / f"source_{source.id}"
    work_dir.mkdir(parents=True, exist_ok=True)
    media = work_dir / "audio.mp3"
    media.write_bytes(b"fake")
    source.file_path = str(media)
    db_session.commit()
    with patch("app.pipeline.probe_duration_seconds", return_value=30), patch(
        "app.pipeline._transcribe_rows", return_value=[(0.0, 1.0, "Treść")]
    ):
        process_upload_source(db_session, source.id, auto_summarize=False)
    db_session.refresh(source)
    assert source.status == "ready"
    assert source.file_path is None
    assert not work_dir.exists()
