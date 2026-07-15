from pathlib import Path

from ebooklib import epub

from app.ingest.epub import extract_epub_text


def test_extract_epub_text(tmp_path: Path):
    book = epub.EpubBook()
    book.set_identifier("id123")
    book.set_title("Demo Book")
    book.set_language("en")
    chapter = epub.EpubHtml(title="Intro", file_name="chap.xhtml", lang="en")
    chapter.content = (
        "<html><body><h1>Intro</h1>"
        "<p>This is a sufficiently long chapter content used for EPUB extraction unit testing in the app.</p>"
        "<p>Another paragraph with more words so the joined document exceeds eighty characters easily.</p>"
        "</body></html>"
    )
    book.add_item(chapter)
    book.toc = (chapter,)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", chapter]
    path = tmp_path / "demo.epub"
    epub.write_epub(str(path), book)

    text = extract_epub_text(path)
    assert "sufficiently long chapter" in text
    assert "Another paragraph" in text
