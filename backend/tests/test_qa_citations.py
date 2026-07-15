from app.llm.qa import _extract_citations, _rank_segments


def test_rank_segments_prefers_keyword_hits():
    segments = [
        (0.0, 2.0, "Opowieść o podróży"),
        (2.0, 4.0, "Dodajemy paprykę i cumin"),
        (4.0, 6.0, "Na koniec odpoczynek"),
    ]
    ranked = _rank_segments(segments, "Jaką paprykę dodać?", limit=2)
    texts = [seg[2] for seg in ranked]
    assert any(t.startswith("Dodajemy paprykę") for t in texts)


def test_extract_citations_from_answer():
    segments = [
        (12.0, 15.0, "Smaż cebulę na małym ogniu"),
        (40.0, 44.0, "Dodaj czosnek"),
    ]
    answer = "Najpierw cebula [00:12], później czosnek [00:40]."
    citations = _extract_citations(answer, segments)
    assert len(citations) == 2
    assert citations[0].timestamp == "00:12"
    assert "Smaż" in citations[0].text