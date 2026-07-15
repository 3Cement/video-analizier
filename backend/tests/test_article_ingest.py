from unittest.mock import MagicMock, patch

from app.ingest.article import fetch_article


def test_fetch_article_extracts_main_text():
    html = """
    <html><head><title>Example Title</title></head>
    <body>
      <nav>ignore nav</nav>
      <article>
        <h1>Example Title</h1>
        <p>This paragraph contains enough characters to pass the extraction threshold for articles in the pipeline.</p>
        <p>Second paragraph also contains meaningful content about podcasts, audiobooks and knowledge tools.</p>
      </article>
    </body></html>
    """
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.text = html
    response.url = "https://example.com/post"
    response.headers = {"content-type": "text/html"}

    with patch("app.ingest.article.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.get.return_value = response
        result = fetch_article("https://example.com/post")

    assert result.title == "Example Title"
    assert "enough characters" in result.text
    assert "ignore nav" not in result.text
