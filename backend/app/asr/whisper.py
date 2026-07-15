from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.config import Settings, get_settings


@dataclass
class AsrSegment:
    start: float
    end: float
    text: str


_model = None
_model_key: Optional[tuple[str, str, str]] = None


def _get_model(settings: Settings):
    global _model, _model_key
    key = (settings.whisper_model, settings.whisper_device, settings.whisper_compute_type)
    if _model is not None and _model_key == key:
        return _model

    from faster_whisper import WhisperModel

    _model = WhisperModel(
        settings.whisper_model,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )
    _model_key = key
    return _model


def transcribe_audio(
    audio_path: Path,
    language: Optional[str] = None,
    settings: Optional[Settings] = None,
) -> list[AsrSegment]:
    settings = settings or get_settings()
    model = _get_model(settings)
    lang = language or settings.whisper_language or None

    segments_iter, _info = model.transcribe(
        str(audio_path),
        language=lang,
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )

    result: list[AsrSegment] = []
    for seg in segments_iter:
        text = (seg.text or "").strip()
        if not text:
            continue
        result.append(AsrSegment(start=float(seg.start), end=float(seg.end), text=text))
    return result