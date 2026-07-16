from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup
from ebooklib import ITEM_DOCUMENT, epub


@dataclass
class EpubChapter:
    title: str
    text: str


def extract_epub_chapters(path: Path) -> list[EpubChapter]:
    book = epub.read_epub(str(path))
    chapters: list[EpubChapter] = []
    for idx, item in enumerate(book.get_items_of_type(ITEM_DOCUMENT), start=1):
        soup = BeautifulSoup(item.get_content(), "lxml")
        for tag in soup(["script", "style"]):
            tag.decompose()
        heading = soup.find(["h1", "h2", "h3"])
        title = heading.get_text(" ", strip=True) if heading else Path(item.get_name()).stem
        title = re.sub(r"\s+", " ", title or f"Chapter {idx}").strip()
        text = soup.get_text("\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if len(text) < 40:
            continue
        chapters.append(EpubChapter(title=title, text=text))
    if not chapters:
        raise RuntimeError("EPUB text extraction produced too little content")
    return chapters


def extract_epub_text(path: Path) -> str:
    return "\n\n".join(f"# {c.title}\n\n{c.text}" for c in extract_epub_chapters(path))


def chapters_to_segments(chapters: list[EpubChapter]) -> list[tuple[float, float, str]]:
    rows: list[tuple[float, float, str]] = []
    t = 0.0
    for chapter in chapters:
        chunk = f"{chapter.title}\n\n{chapter.text}".strip()
        start = t
        end = t + max(8.0, len(chunk) / 14.0)
        rows.append((start, end, chunk))
        t = end
    return rows
