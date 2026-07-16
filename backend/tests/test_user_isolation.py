from app.models import Segment, Source, Summary


def test_x_user_id_cannot_access_other_users_source(client, db_session):
    owned = Source(user_id="other-user", source_type="text", title="Secret", status="ready", transcript_method="text")
    db_session.add(owned)
    db_session.flush()
    db_session.add(Segment(source_id=owned.id, start=0, end=1, text="Tajne.", ord=0))
    db_session.add(Summary(source_id=owned.id, kind="briefing", content="Brief"))
    db_session.commit()
    assert client.get(f"/api/sources/{owned.id}", headers={"X-User-ID": "other-user"}).status_code == 404
    assert client.delete(f"/api/sources/{owned.id}", headers={"X-User-ID": "other-user"}).status_code == 404
