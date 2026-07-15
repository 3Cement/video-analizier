from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup
from ebooklib import ITEM_DOCUMENT, epub


def extract_epub_text(path: Path) -> str:
    book = epub.read_epub(str(path))
    parts: list[str] = []
    for item in book.get_items_of_type(ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "lxml")
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text(chr(10), strip=True)
        text = re.sub(r"\n{3,}", chr(10)+chr(10), text).strip()
        if len(text) >= 40:
            parts.append(text)
    joined = (chr(10)+chr(10)).join(parts).strip()
    if len(joined) < 80:
        raise RuntimeError("EPUB text extraction produced too little content")
    return joined
