from unittest.mock import patch

from app.ingest.podcast import PodcastEpisode


def test_create_article_endpoint(client):
    with patch("app.api.routes.run_in_background") as bg:
        res = client.post(
            "/api/sources/article",
            json={"url": "https://example.com/a", "auto_summarize": False},
        )
        assert res.status_code == 200, res.text
        assert res.json()["source_type"] == "article"
        assert bg.called


def test_create_podcast_endpoint(client):
    with patch("app.api.routes.run_in_background") as bg:
        res = client.post(
            "/api/sources/podcast",
            json={"url": "https://cdn.example.com/ep.mp3", "auto_summarize": False},
        )
        assert res.status_code == 200, res.text
        assert res.json()["source_type"] == "podcast"
        assert bg.called


def test_create_podcast_rss_endpoint(client):
    episodes = [
        PodcastEpisode(title="A", audio_url="https://cdn.example.com/a.mp3"),
        PodcastEpisode(title="B", audio_url="https://cdn.example.com/b.mp3"),
    ]
    with patch("app.api.routes.fetch_rss_episodes", return_value=episodes), patch(
        "app.api.routes.run_in_background"
    ) as bg:
        res = client.post(
            "/api/sources/podcast/rss",
            json={"feed_url": "https://example.com/feed.xml", "max_episodes": 2, "auto_summarize": False},
        )
        assert res.status_code == 200, res.text
        assert len(res.json()) == 2
        assert bg.call_count == 2


def test_url_router_youtube(client):
    with patch("app.api.routes.run_in_background"):
        res = client.post(
            "/api/sources/url",
            json={"url": "https://www.youtube.com/watch?v=abcdefghijk", "auto_summarize": False},
        )
        assert res.status_code == 200, res.text
        assert res.json()["source_type"] == "youtube"
