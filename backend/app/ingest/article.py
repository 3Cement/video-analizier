from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

try:
    import trafilatura
except ImportError:  # pragma: no cover
    trafilatura = None

_UA = (
    "Mozilla/5.0 (compatible; video-analizier/0.3; +https://github.com/3Cement/video-analizier)"
)


@dataclass
class ArticleIngestResult:
    title: str
    url: str
    text: str
    author: str | None = None


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _fallback_bs4(body: str, final_url: str, parsed) -> ArticleIngestResult:
    soup = BeautifulSoup(body, "lxml")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "aside", "form", "iframe"]):
        tag.decompose()

    title = ""
    if soup.title and soup.title.string:
        title = _clean_text(soup.title.string)
    h1 = soup.find("h1")
    if h1:
        title = _clean_text(h1.get_text(" ", strip=True)) or title

    root = soup.find("article") or soup.find("main") or soup.body
    if root is None:
        raise RuntimeError("Could not extract article content")

    chunks: list[str] = []
    for node in root.find_all(["h1", "h2", "h3", "p", "li", "blockquote"]):
        text = _clean_text(node.get_text(" ", strip=True))
        if not text:
            continue
        if len(text) < 25 and node.name not in {"h1", "h2", "h3"}:
            continue
        chunks.append(text)

    text = "\n\n".join(chunks).strip()
    if len(text) < 80:
        text = _clean_text(root.get_text("\n", strip=True))
    if len(text) < 80:
        raise RuntimeError("Extracted article text is too short")
    return ArticleIngestResult(title=title or "Article", url=final_url, text=text)


def fetch_article(url: str, timeout: float = 45.0) -> ArticleIngestResult:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Article URL must be http(s)")

    with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": _UA}) as client:
        response = client.get(url)
        response.raise_for_status()
        final_url = str(response.url)
        body = response.text
        content_type = response.headers.get("content-type", "")

    if "html" not in content_type and "<html" not in body[:800].lower():
        text = body.strip()
        if len(text) < 80:
            raise RuntimeError("Empty article body")
        title = parsed.path.rsplit("/", 1)[-1] or "Article"
        return ArticleIngestResult(title=title, url=final_url, text=text)

    if trafilatura is not None:
        extracted = trafilatura.extract(
            body,
            include_comments=False,
            include_tables=True,
            favor_recall=True,
            url=final_url,
        )
        meta = trafilatura.extract_metadata(body, default_url=final_url)
        title = ""
        author = None
        if meta is not None:
            title = _clean_text(getattr(meta, "title", "") or "")
            author = _clean_text(getattr(meta, "author", "") or "") or None
        if extracted and len(extracted.strip()) >= 80:
            if not title:
                soup = BeautifulSoup(body, "lxml")
                title = _clean_text(soup.title.string) if soup.title and soup.title.string else "Article"
            return ArticleIngestResult(
                title=title or "Article",
                url=final_url,
                text=extracted.strip(),
                author=author,
            )

    return _fallback_bs4(body, final_url, parsed)
