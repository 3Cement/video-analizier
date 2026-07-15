from unittest.mock import patch

from app.llm.summarize import summarize_segments


def test_llm_briefing_schema(monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()

    segments = [
        (0.0, 8.0, "Domowe treningi wymagają 15 do 25 minut pięć razy w tygodniu."),
        (20.0, 28.0, "Najważniejszy problem to brak czasu i brak planu."),
    ]

    with patch("app.llm.summarize.chat_completion") as mock_chat:
        mock_chat.return_value = (
            "# Podsumowanie: Dom\n\n"
            "## W skrócie\n"
            "Krótki opis [00:00].\n\n"
            "## Najważniejsze wnioski\n"
            "- [00:20] Brak planu\n"
        )
        out = summarize_segments(segments, title="Dom", kind="briefing")

    assert out.startswith("# Podsumowanie:")
    assert "Najważniejsze wnioski" in out
    mock_chat.assert_called_once()
    get_settings.cache_clear()
