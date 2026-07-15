from __future__ import annotations

from typing import Optional

from app.chunking import chunk_segments, format_timestamp
from app.config import Settings, get_settings
from app.llm.client import chat_completion

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

    # Evenly sample across the timeline for a better overview without LLM.
    picks: list[tuple[float, float, str]] = []
    last_idx = -999
    for i in range(count):
        idx = round(i * (len(useful) - 1) / (count - 1))
        if idx == last_idx:
            continue
        picks.append(useful[idx])
        last_idx = idx
    return picks


def _extractive_briefing(
    segments: list[tuple[float, float, str]],
    title: str,
    kind: str = "briefing",
) -> str:
    picks = _pick_representative_segments(segments, count=10)
    points = [f"- [{format_timestamp(start)}] {text}" for start, _end, text in picks]
    joined = "\n".join(points) if points else "- (brak segmentów)"
    opener = picks[0][2] if picks else ""
    note = (
        "_Podsumowanie ekstraktywne (brak OPENAI_API_KEY). "
        "Ustaw klucz, aby dostać syntezę NotebookLM-style._"
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
    return (
        f"# Briefing: {title or 'Źródło'}\n\n"
        "## Przegląd\n"
        f"{opener}\n\n"
        f"{note}\n\n"
        "## Kluczowe punkty z materiału\n"
        f"{joined}\n"
    )


def summarize_segments(
    segments: list[tuple[float, float, str]],
    title: str = "",
    kind: str = "briefing",
    settings: Optional[Settings] = None,
) -> str:
    settings = settings or get_settings()
    if not segments:
        return "Brak treści źródłowej do podsumowania."

    if not settings.openai_api_key:
        return _extractive_briefing(segments, title, kind=kind)

    chunks = chunk_segments(segments, max_chars=2800)

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
            "Create a briefing document with:\n"
            "1) Short overview (3-5 sentences)\n"
            "2) Key points with timestamp citations\n"
            "3) Practical takeaways / steps / ingredients if present\n"
            "4) Open questions or gaps in the source"
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