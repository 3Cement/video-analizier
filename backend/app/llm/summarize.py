from __future__ import annotations

import re
from typing import Optional

from app.chunking import chunk_segments, format_timestamp
from app.config import Settings, get_settings
from app.llm.client import chat_completion, has_llm_credentials
from app.llm_settings_store import apply_llm_overrides

SYSTEM_PROMPT = """You are a source-grounded research assistant similar to NotebookLM.
Use ONLY the provided transcript/source excerpts.
Write in Polish unless the user asks otherwise.
Include timestamp citations in [mm:ss] form wherever you reference a concrete point.
If information is missing from the source, say so explicitly.
Do not invent facts, ingredients, steps, or claims not present in the source."""


def _local_summary(chunk_text: str, settings: Settings) -> str:
    return chat_completion(
        SYSTEM_PROMPT,
        (
            "Prepare a concise partial summary of this transcript chunk. "
            "Keep key facts, steps, ingredients, and timestamps.\n\n"
            f"{chunk_text}"
        ),
        settings=settings,
        temperature=0.1,
    )


def _pick_representative_segments(
    segments: list[tuple[float, float, str]],
    count: int = 10,
) -> list[tuple[float, float, str]]:
    useful = [(s, e, t.strip()) for s, e, t in segments if len(t.strip()) >= 40]
    if not useful:
        useful = [(s, e, t.strip()) for s, e, t in segments if t.strip()]
    if not useful:
        return []
    if len(useful) <= count:
        return useful

    picks: list[tuple[float, float, str]] = []
    last_idx = -999
    for i in range(count):
        idx = round(i * (len(useful) - 1) / (count - 1))
        if idx == last_idx:
            continue
        picks.append(useful[idx])
        last_idx = idx
    return picks


_NUMBERISH = re.compile(
    r"(\d+\s*[–-]\s*\d+|\d+)\s*(minut|min|razy|tygodni|tygodnia|sekund|miesięcy|miesiące|%)",
    re.I,
)
_HOOKS = (
    "zasad",
    "ważn",
    "klucz",
    "problem",
    "trzeba",
    "musisz",
    "powin",
    "efekt",
    "wnios",
    "benefit",
    "najważniej",
)


def _score_takeaway(text: str) -> int:
    score = 0
    lower = text.lower()
    if _NUMBERISH.search(text):
        score += 3
    score += sum(1 for h in _HOOKS if h in lower)
    if len(text) > 80:
        score += 1
    return score


def _extractive_briefing(
    segments: list[tuple[float, float, str]],
    title: str,
    kind: str = "briefing",
) -> str:
    picks = _pick_representative_segments(segments, count=10)
    scored = sorted(
        (( _score_takeaway(text), start, text) for start, _end, text in segments if len(text.strip()) >= 50),
        key=lambda item: (-item[0], item[1]),
    )
    takeaways = []
    seen = set()
    for score, start, text in scored:
        if score < 2:
            continue
        key = text[:80]
        if key in seen:
            continue
        seen.add(key)
        takeaways.append(f"- [{format_timestamp(start)}] {text.strip()}")
        if len(takeaways) >= 7:
            break

    if not takeaways:
        takeaways = [f"- [{format_timestamp(s)}] {t}" for s, _e, t in picks[:7]]

    opener = picks[0][2] if picks else (takeaways[0][20:] if takeaways else "")
    points = [f"- [{format_timestamp(start)}] {text}" for start, _end, text in picks]
    joined = "\n".join(points) if points else "- (brak segmentów)"
    note = (
        "_Wygenerowano lokalnie bez klucza LLM. "
        "Ustaw klucz OpenAI / Anthropic / Cursor, aby dostać syntezę w stylu NotebookLM._"
    )

    if kind == "faq":
        faqs = []
        for start, _end, text in picks[:6]:
            faqs.append(
                f"**P:** O czym mowa w fragmencie [{format_timestamp(start)}]?\n"
                f"**O:** {text}"
            )
        body = "\n\n".join(faqs) if faqs else "(brak treści)"
        return f"# FAQ: {title or 'Źródło'}\n\n{note}\n\n{body}\n"

    if kind == "study_guide":
        return (
            f"# Study guide: {title or 'Źródło'}\n\n"
            f"{note}\n\n"
            "## Motywy / fragmenty do powtórki\n"
            f"{joined}\n"
        )

    takeaways_block = "\n".join(takeaways) if takeaways else "- (brak)"
    return (
        f"# Podsumowanie: {title or 'Źródło'}\n\n"
        "## W skrócie\n"
        f"{opener}\n\n"
        f"{note}\n\n"
        "## Najważniejsze informacje / wnioski\n"
        f"{takeaways_block}\n\n"
        "## Fragmenty z timeline\n"
        f"{joined}\n"
    )


def summarize_segments(
    segments: list[tuple[float, float, str]],
    title: str = "",
    kind: str = "briefing",
    settings: Optional[Settings] = None,
) -> str:
    settings = apply_llm_overrides(settings or get_settings())
    if not segments:
        return "Brak treści źródłowej do podsumowania."

    if not has_llm_credentials(settings):
        return _extractive_briefing(segments, title, kind=kind)

    chunks = chunk_segments(segments, max_chars=2800)
    max_chunks = max(1, settings.max_summary_chunks)
    if len(chunks) > max_chunks:
        # Keep evenly spaced chunks to bound latency/cost.
        step = (len(chunks) - 1) / (max_chunks - 1) if max_chunks > 1 else 0
        idxs = sorted({round(i * step) for i in range(max_chunks)})
        chunks = [chunks[i] for i in idxs]

    if len(chunks) == 1:
        source_block = chunks[0].text
    else:
        partials: list[str] = []
        for i, chunk in enumerate(chunks, start=1):
            partial = _local_summary(chunk.text, settings)
            partials.append(
                f"### Fragment {i} ({format_timestamp(chunk.start)}-{format_timestamp(chunk.end)})\n{partial}"
            )
        source_block = "\n\n".join(partials)

    kind_instruction = {
        "briefing": (
            "Create a briefing document in Polish with:\n"
            "1) Section 'W skrócie' — 3-5 sentences overview\n"
            "2) Section 'Najważniejsze wnioski' — bullet list with timestamp citations [mm:ss]\n"
            "3) Section 'Liczby i fakty' — concrete numbers, dosages, durations if present\n"
            "4) Section 'Co zrobić dalej' — practical steps/call-to-action grounded in source\n"
            "5) Section 'Cytaty' — 2-4 short quotes with timestamps\n"
            "6) Open questions or gaps in the source\n"
            "Do not invent facts. Prefer citations over paraphrase when uncertain."
        ),
        "faq": "Create an FAQ with 5-8 questions and answers grounded in the source, with timestamps.",
        "study_guide": "Create a study guide: main themes, definitions, and review questions with timestamps.",
    }.get(kind, "Summarize the source with timestamp citations.")

    user_prompt = (
        f"Title: {title or 'Untitled source'}\n"
        f"Output type: {kind}\n\n"
        f"{kind_instruction}\n\n"
        f"SOURCE MATERIAL:\n{source_block}"
    )
    return chat_completion(SYSTEM_PROMPT, user_prompt, settings=settings)
