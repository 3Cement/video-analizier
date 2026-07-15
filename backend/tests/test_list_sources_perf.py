from app.models import Segment, Source


def test_list_sources_returns_counts_without_loading_all_segment_bodies(client, db_session):
    source = Source(user_id="anonymous", source_type="text", title="Counted", status="ready")
    db_session.add(source)
    db_session.flush()
    for i in range(5):
        db_session.add(Segment(source_id=source.id, start=float(i), end=float(i + 1), text=f"seg {i}", ord=i))
    db_session.commit()

    res = client.get("/api/sources")
    assert res.status_code == 200
    body = res.json()
    assert body[0]["segment_count"] == 5
    assert "segments" not in body[0]
