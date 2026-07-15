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


def _extractive_briefing(
    segments: list[tuple[float, float, str]],
    title: str,
) -> str:
    points = []
    for start, _end, text in segments[:12]:
        clean = text.strip()
        if clean:
            points.append(f"- [{format_timestamp(start)}] {clean}")
    joined = "\n".join(points) if points else "- (brak segmentów)"
    return (
        f"# Briefing: {title or 'Źródło'}\n\n"
        "## Przegląd\n"
        "Podsumowanie ekstraktywne (brak OPENAI_API_KEY — użyto fallbacku lokalnego).\n\n"
        "## Kluczowe punkty\n"
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
        return _extractive_briefing(segments, title)

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