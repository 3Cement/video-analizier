from __future__ import annotations

import re
from typing import Optional

from app.chunking import format_timestamp, segments_to_transcript
from app.config import Settings, get_settings
from app.llm.client import chat_completion
from app.schemas import Citation

SYSTEM_PROMPT = """You are a source-grounded Q&A assistant.
Answer ONLY using the provided source transcript.
Always include at least one timestamp citation in [mm:ss] or [hh:mm:ss] form when the answer is supported.
If the answer is not in the source, say that clearly in Polish.
Respond in Polish."""

_TS_RE = re.compile(r"\[(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\]")


def _ts_to_seconds(match: re.Match[str]) -> float:
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    return hours * 3600 + minutes * 60 + seconds


def _rank_segments(
    segments: list[tuple[float, float, str]],
    question: str,
    limit: int = 24,
) -> list[tuple[float, float, str]]:
    tokens = {t.lower() for t in re.findall(r"\w+", question, flags=re.UNICODE) if len(t) > 2}
    if not tokens:
        return segments[:limit]

    scored: list[tuple[int, tuple[float, float, str]]] = []
    for seg in segments:
        text = seg[2].lower()
        score = sum(1 for tok in tokens if tok in text)
        scored.append((score, seg))
    scored.sort(key=lambda item: (-item[0], item[1][0]))
    top = [seg for score, seg in scored if score > 0][:limit]
    if len(top) < 8:
        # mix in chronological coverage for short sources
        chrono = segments[: max(0, 8 - len(top))]
        seen = {(s[0], s[2]) for s in top}
        for seg in chrono:
            key = (seg[0], seg[2])
            if key not in seen:
                top.append(seg)
    top.sort(key=lambda s: s[0])
    return top


def _extract_citations(
    answer: str,
    segments: list[tuple[float, float, str]],
) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[str] = set()
    for match in _TS_RE.finditer(answer):
        ts = match.group(0)
        if ts in seen:
            continue
        seen.add(ts)
        target = _ts_to_seconds(match)
        best = min(segments, key=lambda s: abs(s[0] - target), default=None)
        if best is None:
            continue
        citations.append(
            Citation(
                start=best[0],
                end=best[1],
                timestamp=format_timestamp(best[0]),
                text=best[2],
            )
        )
    if not citations and segments:
        best = segments[0]
        citations.append(
            Citation(
                start=best[0],
                end=best[1],
                timestamp=format_timestamp(best[0]),
                text=best[2],
            )
        )
    return citations[:8]


def _extractive_answer(
    question: str,
    segments: list[tuple[float, float, str]],
) -> tuple[str, list[Citation]]:
    ranked = _rank_segments(segments, question, limit=6)
    # Prefer segments that actually matched keywords
    tokens = {t.lower() for t in re.findall(r"\w+", question, flags=re.UNICODE) if len(t) > 3}
    matched = [
        seg
        for seg in ranked
        if any(tok in seg[2].lower() for tok in tokens)
    ] or ranked[:4]
    if not matched:
        return "Nie znaleziono pasujących fragmentów w źródle.", []
    lines = [f"- [{format_timestamp(start)}] {text}" for start, _end, text in matched[:5]]
    answer = (
        "Na podstawie źródła (tryb ekstraktywny, brak OPENAI_API_KEY):\n"
        + "\n".join(lines)
    )
    citations = [
        Citation(
            start=start,
            end=end,
            timestamp=format_timestamp(start),
            text=text,
        )
        for start, end, text in matched[:5]
    ]
    return answer, citations


def answer_question(
    question: str,
    segments: list[tuple[float, float, str]],
    title: str = "",
    settings: Optional[Settings] = None,
) -> tuple[str, list[Citation]]:
    settings = settings or get_settings()
    if not segments:
        return "Brak zaindeksowanego źródła do odpowiedzi.", []

    if not settings.openai_api_key:
        return _extractive_answer(question, segments)

    selected = _rank_segments(segments, question)
    # Prefer full transcript for shorter sources
    full_len = sum(len(s[2]) for s in segments)
    if full_len < 12000:
        selected = segments

    transcript = segments_to_transcript(selected, with_timestamps=True)
    user_prompt = (
        f"Title: {title or 'Untitled'}\n"
        f"Question: {question}\n\n"
        f"SOURCE TRANSCRIPT:\n{transcript}\n\n"
        "Write a grounded answer with timestamp citations."
    )
    answer = chat_completion(SYSTEM_PROMPT, user_prompt, settings=settings)
    citations = _extract_citations(answer, segments)
    return answer, citations