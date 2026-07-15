from app.chunking import chunk_segments, format_timestamp, segments_to_transcript


def test_format_timestamp():
    assert format_timestamp(65) == "01:05"
    assert format_timestamp(3661) == "01:01:01"


def test_chunk_segments_merges_and_keeps_ranges():
    segments = [
        (0.0, 2.0, "Pierwszy fragment tekstu o gotowaniu."),
        (2.0, 4.0, "Drugi fragment z kolejnymi wskazówkami."),
        (4.0, 6.0, "Trzeci fragment zamyka myśl."),
    ]
    chunks = chunk_segments(segments, max_chars=80)
    assert len(chunks) >= 1
    assert chunks[0].start == 0.0
    assert "[00:00]" in chunks[0].text


def test_segments_to_transcript():
    text = segments_to_transcript([(12.0, 15.0, "Sól i pieprz")], with_timestamps=True)
    assert text == "[00:12] Sól i pieprz"