from unittest.mock import patch

from app.models import Segment, Source, Summary


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_create_text_source_and_ask(client, db_session):
    with patch("app.api.routes.run_in_background") as bg:
        res = client.post(
            "/api/sources/text",
            json={
                "title": "Przepis testowy",
                "text": "Najpierw podsmaż cebulę. Potem dodaj jajka i sól.",
                "auto_summarize": False,
            },
        )
        assert res.status_code == 200
        source_id = res.json()["id"]
        assert bg.called

    source = db_session.get(Source, source_id)
    source.status = "ready"
    db_session.add(
        Segment(source_id=source_id, start=0.0, end=5.0, text="Najpierw podsmaż cebulę.", ord=0)
    )
    db_session.add(
        Segment(source_id=source_id, start=5.0, end=10.0, text="Potem dodaj jajka i sól.", ord=1)
    )
    db_session.add(Summary(source_id=source_id, kind="briefing", content="Krótki briefing"))
    db_session.commit()

    detail = client.get(f"/api/sources/{source_id}")
    assert detail.status_code == 200
    assert detail.json()["segment_count"] == 2
    assert detail.json()["summaries"][0]["content"] == "Krótki briefing"

    with patch("app.api.routes.answer_question") as ask_mock:
        ask_mock.return_value = (
            "Najpierw cebula [00:00], potem jajka [00:05].",
            [],
        )
        ask = client.post("/api/ask", json={"source_id": source_id, "question": "Jakie są kroki?"})
        assert ask.status_code == 200
        assert "cebula" in ask.json()["answer"]


def test_youtube_create_queues_job(client):
    with patch("app.api.routes.run_in_background") as bg:
        res = client.post(
            "/api/sources/youtube",
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "auto_summarize": False},
        )
        assert res.status_code == 200
        assert res.json()["source_type"] == "youtube"
        assert bg.called


def test_reprocess_and_delete(client, db_session):
    source = Source(
        source_type="youtube",
        title="Do usuniecia",
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        status="ready",
        transcript_method="captions",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)

    with patch("app.api.routes.run_in_background") as bg:
        res = client.post(f"/api/sources/{source.id}/reprocess", json={"force_asr": False})
        assert res.status_code == 200
        assert bg.called

    deleted = client.delete(f"/api/sources/{source.id}")
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"
    assert db_session.get(Source, source.id) is None