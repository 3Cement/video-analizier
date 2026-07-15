from unittest.mock import patch

from app.models import Source
from app.worker import _dispatch, claim_next_pending, run_worker_once


def test_claim_next_pending(db_session):
    source = Source(source_type="youtube", title="Q", status="pending", user_id="anonymous")
    db_session.add(source)
    db_session.commit()

    claimed = claim_next_pending(db_session)
    assert claimed is not None
    assert claimed.id == source.id
    assert claimed.status == "downloading"

    second = claim_next_pending(db_session)
    assert second is None


def test_worker_dispatches_text_via_upload(db_session, tmp_path, monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("MEDIA_DIR", str(tmp_path / "media"))
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("CURSOR_API_KEY", "")
    get_settings.cache_clear()
    settings = get_settings()

    source = Source(source_type="text", title="Note", status="pending", user_id="anonymous")
    db_session.add(source)
    db_session.commit()
    dest_dir = settings.media_dir / f"source_{source.id}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "content.txt"
    dest.write_text("Tekst testowy do przetwarzania pracownika.", encoding="utf-8")
    source.file_path = str(dest)
    db_session.commit()

    assert run_worker_once(db_session) is True
    db_session.refresh(source)
    assert source.status == "ready"
    assert source.segments
    get_settings.cache_clear()


def test_dispatch_youtube_calls_pipeline(db_session):
    source = Source(source_type="youtube", title="Y", status="downloading", user_id="anonymous")
    db_session.add(source)
    db_session.commit()
    with patch("app.worker.process_youtube_source") as proc:
        _dispatch(db_session, source)
        proc.assert_called_once()
