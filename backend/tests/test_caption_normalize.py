from app.ingest.captions import CaptionSegment, clean_caption_text, normalize_caption_stream
from app.ingest.youtube import parse_vtt


def test_clean_caption_text_unescapes_and_strips_music():
    raw = "ćwiczyć, żeby widzieć &gt;&gt; [muzyka] efekty"
    assert clean_caption_text(raw) == "ćwiczyć, żeby widzieć efekty"


def test_normalize_rolling_auto_captions():
    raw = [
        CaptionSegment(0.0, 2.0, "Zapewne widziałeś kiedyś reklamy"),
        CaptionSegment(1.5, 3.5, "widziałeś kiedyś reklamy które obiecują"),
        CaptionSegment(3.0, 5.0, "reklamy które obiecują transformacje"),
    ]
    out = normalize_caption_stream(raw)
    joined = " ".join(s.text for s in out)
    assert "Zapewne" in joined
    assert "transformacje" in joined
    assert joined.count("widziałeś kiedyś reklamy") == 1


def test_parse_vtt_normalizes_entities():
    content = """WEBVTT

00:00:01.000 --> 00:00:03.000
Test &gt;&gt; [muzyka] zdanie

00:00:02.500 --> 00:00:05.000
zdanie kolejne słowa
"""
    segs = parse_vtt(content)
    assert segs
    assert all("&gt;" not in s.text for s in segs)
    assert all("[muzyka]" not in s.text.lower() for s in segs)


def test_normalize_keeps_sentence_boundary_together():
    raw = [
        CaptionSegment(0.0, 2.0, "I prawda jest"),
        CaptionSegment(2.0, 5.0, "taka, że one nie kłamią."),
        CaptionSegment(5.5, 8.0, "Zaczynamy od treningu."),
    ]
    out = normalize_caption_stream(raw)
    assert any("prawda jest taka" in s.text for s in out)
    assert any(s.text.startswith("Zaczynamy") for s in out)