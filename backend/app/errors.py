from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class JobError:
    message: str
    code: str
    hint: str


_BOT_RE = re.compile(r"bot|sign in|confirm you're not|429|too many requests", re.I)
_PRIVATE_RE = re.compile(r"private|members.?only|unavailable|removed|copyright", re.I)
_NETWORK_RE = re.compile(r"timed out|connection|network|dns|unreachable|403|502|503", re.I)
_FORMAT_RE = re.compile(r"unsupported url|invalid url|no video formats|format", re.I)
_DURATION_RE = re.compile(r"duration|too long|max.*length", re.I)


def classify_job_error(exc: BaseException) -> JobError:
    message = str(exc).strip() or exc.__class__.__name__
    lower = message.lower()

    if _BOT_RE.search(lower):
        return JobError(
            message=message,
            code="youtube_bot_check",
            hint=(
                "YouTube blokuje pobieranie z tego serwera. "
                "Ustaw YTDLP_PROXY i/lub YTDLP_COOKIES w .env."
            ),
        )
    if _PRIVATE_RE.search(lower):
        return JobError(
            message=message,
            code="youtube_unavailable",
            hint="Film jest prywatny, usunięty lub niedostępny w Twoim regionie.",
        )
    if _DURATION_RE.search(lower):
        return JobError(
            message=message,
            code="video_too_long",
            hint="Film przekracza dozwoloną długość. Skróć materiał lub zwiększ limit.",
        )
    if _FORMAT_RE.search(lower):
        return JobError(
            message=message,
            code="youtube_format",
            hint="Nie udało się pobrać audio. Sprawdź poprawność linku YouTube.",
        )
    if _NETWORK_RE.search(lower):
        return JobError(
            message=message,
            code="network",
            hint="Problem sieciowy podczas pobierania. Spróbuj ponownie za chwilę.",
        )
    return JobError(
        message=message,
        code="processing_failed",
        hint="Przetwarzanie nie powiodło się. Użyj ponownej analizy lub force ASR.",
    )
