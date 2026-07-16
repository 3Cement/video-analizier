from __future__ import annotations

import re
from typing import Optional

from app.chunking import format_timestamp, segments_to_transcript
from app.config import Settings, get_settings
from app.llm.client import chat_completion, has_llm_credentials
from app.schemas import Citation

SYSTEM_PROMPT = """You are a source-grounded Q&A assistant.
Answer ONLY using the provided source transcript.
Always include at least one timestamp citation in [mm:ss] or [hh:mm:ss] form when the answer is supported.
If the answer is not in the source, say that clearly in Polish.
Respond in Polish."""

_TS_RE = re.compile(r"\[(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\]")
_STOPWORDS = {
    "jaki",
    "jaka",
    "jakie",
    "jaką",
    "ile",
    "czy",
    "jest",
    "są",
    "oraz",
    "żeby",
    "aby",
    "tego",
    "tym",
    "tej",
    "dla",
    "bez",
    "nie",
    "tak",
    "się",
    "po",
    "na",
    "do",
    "od",
    "za",
    "co",
    "w",
    "z",
    "i",
    "a",
    "o",
    "u",
}


def _stem_token(token: str) -> str:
    """Very light Polish stemming for keyword matching."""
    t = token.lower()
    for suffix in (
        "ami",
        "ach",
        "owi",
        "owie",
        "ych",
        "ich",
        "ego",
        "emu",
        "ymi",
        "imi",
        "ymi",
        "iem",
        "om",
        "em",
        "ie",
        "ów",
        "ą",
        "ę",
        "u",
        "y",
        "i",
        "a",
        "e",
        "o",
    ):
        if len(t) > len(suffix) + 3 and t.endswith(suffix):
            return t[: -len(suffix)]
    return t


def _question_stems(question: str) -> set[str]:
    tokens = re.findall(r"\w+", question.lower(), flags=re.UNICODE)
    stems = set()
    for tok in tokens:
        if len(tok) <= 2 or tok in _STOPWORDS:
            continue
        stems.add(_stem_token(tok))
    return stems


def _ts_to_seconds(match: re.Match[str]) -> float:
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    return hours * 3600 + minutes * 60 + seconds


from app.llm.retrieval import retrieve_segments


def _rank_segments(
    segments: list[tuple[float, float, str]],
    question: str,
    limit: int = 24,
) -> list[tuple[float, float, str]]:
    return retrieve_segments(segments, question, limit=limit)


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
    ranked = _rank_segments(segments, question, limit=8)
    stems = _question_stems(question)
    matched = []
    for seg in ranked:
        words = re.findall(r"\w+", seg[2].lower(), flags=re.UNICODE)
        seg_stems = {_stem_token(w) for w in words if len(w) > 2}
        score = sum(1 for stem in stems if stem in seg_stems or any(stem in s for s in seg_stems))
        if "ile" in question.lower() and re.search(r"\d", seg[2]):
            score += 2
        if score > 0:
            matched.append((score, seg))
    matched.sort(key=lambda item: (-item[0], item[1][0]))
    chosen = [seg for _score, seg in matched[:4]] or ranked[:3]
    if not chosen:
        return "Nie znaleziono pasujących fragmentów w źródle.", []
    chosen.sort(key=lambda s: s[0])
    lines = [f"- [{format_timestamp(start)}] {text}" for start, _end, text in chosen]
    answer = (
        "Na podstawie źródła (tryb ekstraktywny, brak klucza LLM):\n" + "\n".join(lines)
    )
    citations = [
        Citation(
            start=start,
            end=end,
            timestamp=format_timestamp(start),
            text=text,
        )
        for start, end, text in chosen
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

    if not has_llm_credentials(settings):
        return _extractive_answer(question, segments)

    selected = _rank_segments(segments, question, limit=18)
    full_len = sum(len(s[2]) for s in segments)
    # Keep full transcript only for short sources; otherwise retrieval-first.
    if full_len < 4000:
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
