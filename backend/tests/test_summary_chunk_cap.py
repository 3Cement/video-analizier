from unittest.mock import patch

from app.config import Settings
from app.llm.summarize import summarize_segments


def test_max_summary_chunks_limits_llm_calls():
    segments = [(float(i * 10), float(i * 10 + 5), f"Segment number {i} with enough text content here.") for i in range(40)]
    settings = Settings(openai_api_key="k", max_summary_chunks=3)
    with patch("app.llm.summarize.chat_completion", return_value="# Podsumowanie\n\nok") as mock_chat:
        with patch("app.llm.summarize.chunk_segments") as chunk_mock:
            chunk_mock.return_value = [
                type("C", (), {"start": float(i), "end": float(i + 1), "text": f"chunk {i} " * 20})()
                for i in range(10)
            ]
            out = summarize_segments(segments, title="Cap", kind="briefing", settings=settings)
    assert out.startswith("#")
    # 3 local summaries + 1 final synthesize
    assert mock_chat.call_count == 4
