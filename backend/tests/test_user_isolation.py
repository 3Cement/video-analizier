from app.models import Segment, Source, Summary


def test_cannot_access_other_users_source(client, db_session):
    owned = Source(
        user_id="alice",
        source_type="text",
        title="Alice note",
        status="ready",
        transcript_method="text",
    )
    db_session.add(owned)
    db_session.flush()
    db_session.add(Segment(source_id=owned.id, start=0.0, end=1.0, text="Tajne.", ord=0))
    db_session.add(Summary(source_id=owned.id, kind="briefing", content="Brief"))
    db_session.commit()

    denied = client.get(f"/api/sources/{owned.id}", headers={"X-User-Id": "bob"})
    assert denied.status_code == 404

    allowed = client.get(f"/api/sources/{owned.id}", headers={"X-User-Id": "alice"})
    assert allowed.status_code == 200
    assert allowed.json()["title"] == "Alice note"

    delete_denied = client.delete(f"/api/sources/{owned.id}", headers={"X-User-Id": "bob"})
    assert delete_denied.status_code == 404
