from app.llm.retrieval import retrieve_segments


def test_retrieval_prefers_matching_segment():
    segments = [
        (0.0, 5.0, "Rozgrzewka barków trwa dwie minuty."),
        (10.0, 15.0, "Swingi kettlebell robimy trzy serie po piętnaście."),
        (20.0, 25.0, "Odpoczynek między seriami to czterdzieści pięć sekund."),
    ]
    ranked = retrieve_segments(segments, "Ile serii swingów?", limit=2)
    assert ranked
    assert any("serie" in seg[2].lower() for seg in ranked)
