from app.ingest.youtube import parse_json3, parse_vtt


def test_parse_vtt_basic():
    content = """WEBVTT

00:00:01.000 --> 00:00:03.500
Witajcie w kuchni

00:00:03.500 --> 00:00:06.000
Dziś robimy omlet
"""
    segs = parse_vtt(content)
    assert len(segs) == 2
    assert segs[0].text == "Witajcie w kuchni"
    assert segs[0].start == 1.0
    assert segs[1].end == 6.0


def test_parse_json3_basic():
    content = """{
      "events": [
        {"tStartMs": 1000, "dDurationMs": 2000, "segs": [{"utf8": "Cześć "}, {"utf8": "świecie"}]},
        {"tStartMs": 4000, "dDurationMs": 1000, "segs": [{"utf8": "\\n"}]}
      ]
    }"""
    segs = parse_json3(content)
    assert len(segs) == 1
    assert segs[0].text == "Cześć świecie"
    assert segs[0].start == 1.0
    assert segs[0].end == 3.0