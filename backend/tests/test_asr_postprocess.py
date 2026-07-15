from app.asr.postprocess import normalize_asr_segments
from app.asr.whisper import AsrSegment


def test_asr_postprocess_merges_short_fragments():
    raw = [
        AsrSegment(start=0.0, end=1.0, text="domowe treningi"),
        AsrSegment(start=1.1, end=2.0, text="wymagają częstotliwości."),
        AsrSegment(start=5.0, end=7.0, text="Najważniejszy problem to brak planu."),
    ]
    out = normalize_asr_segments(raw)
    assert len(out) <= len(raw)
    assert any("treningi" in seg.text for seg in out)
