from unittest.mock import patch

from app.models import Segment, Source


def test_ask_is_persisted(client, db_session):
    source = Source(source_type="text", title="Test", status="ready", transcript_method="text")
    db_session.add(source)
    db_session.flush()
    db_session.add(Segment(source_id=source.id, start=0.0, end=1.0, text="Trening trwa 20 minut.", ord=0))
    db_session.commit()

    with patch("app.api.routes.answer_question") as ask_mock:
        ask_mock.return_value = ("Odpowiedź [00:00].", [])
        res = client.post("/api/ask", json={"source_id": source.id, "question": "Jak długo?"})
        assert res.status_code == 200

    asks = client.get(f"/api/sources/{source.id}/asks")
    assert asks.status_code == 200
    body = asks.json()
    assert len(body) == 1
    assert body[0]["question"] == "Jak długo?"
