from app.llm.summarize import summarize_segments


def test_extractive_faq_kind(monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    segments = [
        (0.0, 5.0, "Swingi kettlebell robić trzy serie po piętnaście."),
        (20.0, 25.0, "Odpoczynek między seriami to czterdzieści pięć sekund."),
    ]
    out = summarize_segments(segments, title="Plan", kind="faq")
    assert out.startswith("# FAQ:")
    assert "P:" in out
    assert "Swingi" in out
    get_settings.cache_clear()


def test_extractive_briefing_kind(monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    segments = [
        (
            0.0,
            8.0,
            "Domowe treningi wymagają większej częstotliwości: 15 do 25 minut pięć razy w tygodniu.",
        ),
        (20.0, 28.0, "Najważniejszy problem to brak czasu i brak planu treningowego."),
    ]
    out = summarize_segments(segments, title="Dom", kind="briefing")
    assert out.startswith("# Podsumowanie:")
    assert "Najważniejsze informacje" in out
    assert "15" in out
    get_settings.cache_clear()