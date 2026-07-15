from app.ingest.text import text_to_segments


def test_text_to_segments_splits_long_text():
    text = " ".join(["słowo"] * 200)
    segments = text_to_segments(text, chars_per_segment=80)
    assert len(segments) > 1
    assert segments[0][0] == 0.0
    assert all(s[2] for s in segments)