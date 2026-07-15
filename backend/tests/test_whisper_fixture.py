from pathlib import Path
from unittest.mock import patch

from app.asr.postprocess import normalize_asr_segments
from app.asr.whisper import AsrSegment


def test_whisper_pipeline_uses_postprocess():
    fixture_segments = [
        AsrSegment(start=0.0, end=2.0, text="Cześć, tu Maciej."),
        AsrSegment(start=2.1, end=4.0, text="Dziś pokażę trening z kettlebell."),
    ]

    with patch("app.pipeline.transcribe_audio", return_value=fixture_segments):
        from app.pipeline import _transcribe_rows
        from app.config import get_settings

        rows = _transcribe_rows(Path("dummy.mp3"), "pl", get_settings())

    expected = normalize_asr_segments(fixture_segments)
    assert len(rows) == len(expected)
    assert rows[0][2]
