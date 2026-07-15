from __future__ import annotations

import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from app.asr.whisper import transcribe_audio
from app.config import get_settings
from app.ingest.pdf import extract_pdf_text
from app.ingest.text import load_text_file, text_to_segments
from app.ingest.youtube import ingest_youtube, load_local_captions
from app.llm.summarize import summarize_segments
from app.media import probe_duration_seconds
from app.models import Segment, Source, Summary


def _replace_segments(db: Session, source: Source, rows: list[tuple[float, float, str]]) -> None:
    source.segments.clear()
    db.flush()
    for idx, (start, end, text) in enumerate(rows):
        db.add(
            Segment(
                source_id=source.id,
                start=start,
                end=end,
                text=text,
                ord=idx,
            )
        )


def _maybe_summarize(db: Session, source: Source, auto_summarize: bool) -> None:
    if not auto_summarize:
        return
    settings = get_settings()
    segs = [(s.start, s.end, s.text) for s in source.segments]
    content = summarize_segments(segs, title=source.title, kind="briefing", settings=settings)
    db.add(Summary(source_id=source.id, kind="briefing", content=content))


def process_youtube_source(db: Session, source_id: int, auto_summarize: bool = True) -> None:
    settings = get_settings()
    source = db.get(Source, source_id)
    if source is None:
        return

    try:
        source.status = "downloading"
        db.commit()

        work_dir = settings.media_dir / f"source_{source.id}"
        if work_dir.exists():
            shutil.rmtree(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)

        result = ingest_youtube(source.url or "", work_dir, language=source.language)
        source.title = result.title or source.title
        source.duration_seconds = result.duration_seconds
        if result.audio_path:
            source.file_path = str(result.audio_path)

        if result.captions:
            source.status = "transcribing"
            source.transcript_method = "captions"
            db.commit()
            rows = [(c.start, c.end, c.text) for c in result.captions]
        else:
            if not result.audio_path or not Path(result.audio_path).exists():
                raise RuntimeError("No captions and no audio file available for ASR")
            source.status = "transcribing"
            source.transcript_method = "whisper"
            db.commit()
            asr = transcribe_audio(Path(result.audio_path), language=source.language, settings=settings)
            rows = [(s.start, s.end, s.text) for s in asr]

        _replace_segments(db, source, rows)
        db.flush()

        source.status = "summarizing" if auto_summarize else "ready"
        db.commit()

        if auto_summarize:
            source = db.get(Source, source_id)
            assert source is not None
            _maybe_summarize(db, source, auto_summarize=True)

        source = db.get(Source, source_id)
        assert source is not None
        source.status = "ready"
        source.error = None
        db.commit()
    except Exception as exc:  # noqa: BLE001 - persist job failure for API clients
        db.rollback()
        source = db.get(Source, source_id)
        if source is not None:
            source.status = "failed"
            source.error = str(exc)
            db.commit()
        raise


def process_text_source(
    db: Session,
    source_id: int,
    text: str,
    auto_summarize: bool = True,
) -> None:
    source = db.get(Source, source_id)
    if source is None:
        return
    try:
        source.status = "transcribing"
        db.commit()
        rows = text_to_segments(text)
        _replace_segments(db, source, rows)
        db.flush()
        source.status = "summarizing" if auto_summarize else "ready"
        db.commit()
        if auto_summarize:
            source = db.get(Source, source_id)
            assert source is not None
            _maybe_summarize(db, source, auto_summarize=True)
        source = db.get(Source, source_id)
        assert source is not None
        source.status = "ready"
        source.error = None
        source.transcript_method = "text"
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        source = db.get(Source, source_id)
        if source is not None:
            source.status = "failed"
            source.error = str(exc)
            db.commit()
        raise


def process_upload_source(db: Session, source_id: int, auto_summarize: bool = True) -> None:
    settings = get_settings()
    source = db.get(Source, source_id)
    if source is None:
        return
    try:
        path = Path(source.file_path or "")
        if not path.exists():
            raise RuntimeError(f"Uploaded file missing: {path}")

        suffix = path.suffix.lower()
        if suffix == ".pdf":
            source.status = "transcribing"
            source.transcript_method = "pdf"
            db.commit()
            text = extract_pdf_text(path)
            rows = text_to_segments(text)
        elif suffix in {".txt", ".md"}:
            source.status = "transcribing"
            source.transcript_method = "text"
            db.commit()
            text = load_text_file(path)
            rows = text_to_segments(text)
        elif suffix in {".mp3", ".wav", ".m4a", ".webm", ".ogg", ".mp4", ".mkv"}:
            source.status = "transcribing"
            source.transcript_method = "whisper"
            db.commit()
            source.duration_seconds = probe_duration_seconds(path)
            asr = transcribe_audio(path, language=source.language, settings=settings)
            rows = [(s.start, s.end, s.text) for s in asr]
            if source.duration_seconds is None and rows:
                source.duration_seconds = float(rows[-1][1])
        else:
            raise RuntimeError(f"Unsupported file type: {suffix}")

        if not source.title:
            source.title = path.name

        _replace_segments(db, source, rows)
        db.flush()
        source.status = "summarizing" if auto_summarize else "ready"
        db.commit()
        if auto_summarize:
            source = db.get(Source, source_id)
            assert source is not None
            _maybe_summarize(db, source, auto_summarize=True)
        source = db.get(Source, source_id)
        assert source is not None
        source.status = "ready"
        source.error = None
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        source = db.get(Source, source_id)
        if source is not None:
            source.status = "failed"
            source.error = str(exc)
            db.commit()
        raise


def reprocess_source_from_media(
    db: Session,
    source_id: int,
    prefer_captions: bool = True,
    force_asr: bool = False,
    auto_summarize: bool = True,
) -> None:
    """Rebuild segments from already downloaded media (no YouTube re-download)."""
    settings = get_settings()
    source = db.get(Source, source_id)
    if source is None:
        return
    try:
        work_dir = settings.media_dir / f"source_{source.id}"
        if not work_dir.exists():
            raise RuntimeError(f"Media directory missing for source {source_id}")

        source.status = "transcribing"
        source.error = None
        db.commit()

        rows: list[tuple[float, float, str]] = []
        if prefer_captions and not force_asr:
            captions, _lang = load_local_captions(work_dir, language=source.language)
            if captions:
                rows = [(c.start, c.end, c.text) for c in captions]
                source.transcript_method = "captions"

        if not rows:
            audio_candidates = sorted(
                p
                for p in work_dir.iterdir()
                if p.suffix.lower() in {".mp3", ".m4a", ".webm", ".opus", ".wav"}
            )
            if not audio_candidates:
                raise RuntimeError("No captions and no audio available for reprocess")
            asr = transcribe_audio(audio_candidates[0], language=source.language, settings=settings)
            rows = [(s.start, s.end, s.text) for s in asr]
            source.transcript_method = "whisper"

        source.summaries.clear()
        _replace_segments(db, source, rows)
        db.flush()
        source.status = "summarizing" if auto_summarize else "ready"
        db.commit()
        if auto_summarize:
            source = db.get(Source, source_id)
            assert source is not None
            _maybe_summarize(db, source, auto_summarize=True)
        source = db.get(Source, source_id)
        assert source is not None
        source.status = "ready"
        source.error = None
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        source = db.get(Source, source_id)
        if source is not None:
            source.status = "failed"
            source.error = str(exc)
            db.commit()
        raise