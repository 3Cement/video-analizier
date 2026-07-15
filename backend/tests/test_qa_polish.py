from app.llm.qa import _extractive_answer, _question_stems, _rank_segments


def test_question_stems_drop_stopwords():
    stems = _question_stems("Ile razy w tygodniu trzeba ćwiczyć?")
    assert "ile" not in stems
    assert "tygodnie" in stems or "tygodni" in stems or any("tygod" in s for s in stems)
    assert any("cwicz" in s or "ćwicz" in s for s in stems)


def test_rank_prefers_frequency_answer_for_ile_question():
    segments = [
        (0.0, 5.0, "Zapewne widziałeś reklamy o transformacjach"),
        (60.0, 70.0, "Powtórz to pięć, sześć razy w ciągu tygodnia przez 15 do 25 minut"),
        (200.0, 210.0, "Na koniec rozciąganie bioder"),
    ]
    ranked = _rank_segments(segments, "Ile razy w tygodniu trzeba ćwiczyć?", limit=2)
    assert "pięć" in ranked[0][2] or "sześć" in ranked[0][2]


def test_extractive_answer_returns_numeric_hit():
    segments = [
        (0.0, 5.0, "Wstęp o reklamach treningowych"),
        (60.0, 70.0, "Wystarczy 15 do 25 minut pięć razy w tygodniu"),
    ]
    answer, citations = _extractive_answer(
        "Ile minut dziennie wystarczy?",
        segments,
    )
    assert "15" in answer
    assert citations
    assert "15" in citations[0].text
