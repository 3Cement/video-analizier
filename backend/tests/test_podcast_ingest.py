from app.ingest.podcast import parse_rss, resolve_episode_audio


RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Show</title>
    <item>
      <title>Episode One</title>
      <link>https://example.com/ep1</link>
      <enclosure url="https://cdn.example.com/ep1.mp3" type="audio/mpeg" length="123"/>
      <itunes:duration xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">12:34</itunes:duration>
    </item>
    <item>
      <title>Episode Two</title>
      <enclosure url="https://cdn.example.com/ep2.m4a" type="audio/mp4" length="123"/>
    </item>
  </channel>
</rss>
"""


def test_parse_rss_episodes():
    episodes = parse_rss(RSS, max_episodes=1)
    assert len(episodes) == 1
    assert episodes[0].title == "Episode One"
    assert episodes[0].audio_url.endswith("ep1.mp3")
    assert episodes[0].duration_hint == 12 * 60 + 34


def test_resolve_direct_audio_url():
    ep = resolve_episode_audio("https://cdn.example.com/show/episode.mp3")
    assert ep.audio_url.endswith(".mp3")
    assert "episode.mp3" in ep.title
