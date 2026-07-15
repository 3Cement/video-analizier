from unittest.mock import patch

from app.models import Segment, Source, Summary


def test_quota_endpoint(client, db_session):
    res = client.get("/api/quota")
    assert res.status_code == 200
    body = res.json()
    assert "used" in body and "limit" in body and "remaining" in body


def test_share_page_and_export(client, db_session):
    source = Source(
        user_id="anonymous",
        source_type="youtube",
        title="Trening testowy",
        url="https://www.youtube.com/watch?v=tPsVjYR0tGY",
        status="ready",
        transcript_method="captions",
    )
    db_session.add(source)
    db_session.flush()
    db_session.add(Segment(source_id=source.id, start=0.0, end=2.0, text="Zacznij od rozgrzewki.", ord=0))
    db_session.add(
        Summary(
            source_id=source.id,
            kind="briefing",
            content="# Podsumowanie\n\n## W skrócie\nRozgrzewka jest kluczowa [00:00].\n",
        )
    )
    db_session.commit()

    shared = client.post(f"/api/sources/{source.id}/share")
    assert shared.status_code == 200
    slug = shared.json()["share_slug"]
    assert slug

    page = client.get(f"/s/{slug}")
    assert page.status_code == 200
    assert "Trening testowy" in page.text
    assert "Rozgrzewka" in page.text
    assert 'property="og:title"' in page.text

    export = client.get(f"/api/sources/{source.id}/export.md")
    assert export.status_code == 200
    assert "Trening testowy" in export.text
    assert "Rozgrzewka" in export.text


def test_playlist_queues_jobs(client):
    with patch("app.api.routes.run_in_background") as bg:
        res = client.post(
            "/api/sources/playlist",
            json={
                "urls": [
                    "https://www.youtube.com/watch?v=aaaaaaaaaaa",
                    "https://youtu.be/bbbbbbbbbbb",
                ],
                "auto_summarize": False,
            },
        )
        assert res.status_code == 200
        assert len(res.json()) == 2
        assert bg.call_count == 2


def test_robots_and_sitemap(client, db_session):
    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert "Sitemap" in robots.text

    source = Source(
        user_id="anonymous",
        source_type="text",
        title="Public",
        status="ready",
        is_public=True,
        share_slug="abc123share",
    )
    db_session.add(source)
    db_session.commit()

    sm = client.get("/sitemap.xml")
    assert sm.status_code == 200
    assert "/s/abc123share" in sm.text
