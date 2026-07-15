from __future__ import annotations

import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from app.asr.postprocess import normalize_asr_segments
from app.asr.whisper import transcribe_audio
from app.config import get_settings
from app.errors import classify_job_error
from app.ingest.article import fetch_article
from app.ingest.docx_ingest import extract_docx_text
from app.ingest.epub import chapters_to_segments, extract_epub_chapters
from app.ingest.pdf import extract_pdf_text
from app.ingest.podcast import download_audio, resolve_episode_audio
from app.ingest.text import load_text_file, text_to_segments
from app.ingest.youtube import ingest_youtube, load_local_captions
from app.llm.summarize import summarize_segments
from app.limits import check_duration_limit
from app.llm_settings_store import apply_llm_overrides
from app.media import probe_duration_seconds
from app.models import Segment, Source, Summary


def _fail_source(db: Session, source_id: int, exc: BaseException) -> None:
    db.rollback()
    source = db.get(Source, source_id)
    if source is None:
        return
    job_error = classify_job_error(exc)
    source.status = "failed"
    source.error = job_error.message
    source.error_code = job_error.code
    source.error_hint = job_error.hint
    source.progress = 100.0
    source.progress_message = "failed"
    db.commit()


def _set_progress(db: Session, source: Source, status: str, pct: float, message: str) -> None:
    source.status = status
    source.progress = max(0.0, min(100.0, float(pct)))
    source.progress_message = message
    db.commit()


def _transcribe_rows(audio_path: Path, language: str, settings) -> list[tuple[float, float, str]]:
    asr = normalize_asr_segments(transcribe_audio(audio_path, language=language, settings=settings))
    return [(s.start, s.end, s.text) for s in asr]


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
    settings = apply_llm_overrides(get_settings())
    segs = [(s.start, s.end, s.text) for s in source.segments]
    content = summarize_segments(segs, title=source.title, kind="briefing", settings=settings)
    db.add(Summary(source_id=source.id, kind="briefing", content=content))
    if source.source_type in {"article", "book", "podcast", "audiobook", "audio", "pdf", "text"}:
        facts = summarize_segments(segs, title=source.title, kind="facts", settings=settings)
        db.add(Summary(source_id=source.id, kind="facts", content=facts))


def process_youtube_source(db: Session, source_id: int, auto_summarize: bool = True) -> None:
    settings = get_settings()
    source = db.get(Source, source_id)
    if source is None:
        return

    try:
        _set_progress(db, source, "downloading", 5, "Downloading media")

        work_dir = settings.media_dir / f"source_{source.id}"
        if work_dir.exists():
            shutil.rmtree(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)

        result = ingest_youtube(source.url or "", work_dir, language=source.language)
        source.title = result.title or source.title
        source.video_id = result.video_id
        source.duration_seconds = result.duration_seconds
        check_duration_limit(result.duration_seconds, settings)
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
            rows = _transcribe_rows(Path(result.audio_path), source.language, settings)

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
        source.progress = 100.0
        source.progress_message = "ready"
        source.error = None
        source.error_code = None
        source.error_hint = None
        db.commit()
    except Exception as exc:  # noqa: BLE001 - persist job failure for API clients
        _fail_source(db, source_id, exc)
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
        source.progress = 100.0
        source.progress_message = "ready"
        source.error = None
        source.error_code = None
        source.error_hint = None
        source.transcript_method = "text"
        db.commit()
    except Exception as exc:  # noqa: BLE001
        _fail_source(db, source_id, exc)
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
        elif suffix == ".epub":
            _set_progress(db, source, "transcribing", 20, "Extracting EPUB chapters")
            source.transcript_method = "epub"
            source.source_type = "book"
            db.commit()
            chapters = extract_epub_chapters(path)
            rows = chapters_to_segments(chapters)
        elif suffix in {".txt", ".md"}:
            source.status = "transcribing"
            source.transcript_method = "text"
            db.commit()
            text = load_text_file(path)
            rows = text_to_segments(text)
        elif suffix in {".mp3", ".wav", ".m4a", ".m4b", ".webm", ".ogg", ".opus", ".flac", ".aac", ".mp4", ".mkv"}:
            source.status = "transcribing"
            source.transcript_method = "whisper"
            if source.source_type not in {"podcast", "audiobook", "audio"}:
                source.source_type = "audiobook" if suffix == ".m4b" else "audio"
            db.commit()
            source.duration_seconds = probe_duration_seconds(path)
            check_duration_limit(source.duration_seconds, settings, kind="audio")
            rows = _transcribe_rows(path, source.language, settings)
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
        source.progress = 100.0
        source.progress_message = "ready"
        source.error = None
        source.error_code = None
        source.error_hint = None
        db.commit()
    except Exception as exc:  # noqa: BLE001
        _fail_source(db, source_id, exc)
        raise



def process_article_source(db: Session, source_id: int, auto_summarize: bool = True) -> None:
    source = db.get(Source, source_id)
    if source is None:
        return
    try:
        source.status = "downloading"
        db.commit()
        result = fetch_article(source.url or "")
        source.title = result.title or source.title
        source.url = result.url
        source.author = result.author
        _set_progress(db, source, "downloading", 30, "Article downloaded")

        settings = get_settings()
        work_dir = settings.media_dir / f"source_{source.id}"
        work_dir.mkdir(parents=True, exist_ok=True)
        dest = work_dir / "article.txt"
        dest.write_text(result.text, encoding="utf-8")
        source.file_path = str(dest)

        source.status = "transcribing"
        source.transcript_method = "article"
        db.commit()
        rows = text_to_segments(result.text)
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
        source.progress = 100.0
        source.progress_message = "ready"
        source.error = None
        source.error_code = None
        source.error_hint = None
        db.commit()
    except Exception as exc:  # noqa: BLE001
        _fail_source(db, source_id, exc)
        raise


def process_podcast_source(db: Session, source_id: int, auto_summarize: bool = True) -> None:
    settings = get_settings()
    source = db.get(Source, source_id)
    if source is None:
        return
    try:
        source.status = "downloading"
        db.commit()
        episode = resolve_episode_audio(source.url or "")
        source.title = episode.title or source.title
        source.show_title = episode.show_title
        source.description = episode.description
        source.author = episode.author
        source.published_at = episode.published_at
        _set_progress(db, source, "downloading", 25, "Downloading episode audio")
        work_dir = settings.media_dir / f"source_{source.id}"
        work_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(episode.audio_url.split("?", 1)[0]).suffix.lower() or ".mp3"
        if suffix not in {".mp3", ".m4a", ".m4b", ".ogg", ".opus", ".wav", ".flac", ".aac", ".mp4"}:
            suffix = ".mp3"
        dest = work_dir / f"episode{suffix}"
        download_audio(episode.audio_url, dest)
        source.file_path = str(dest)
        source.source_type = "podcast"
        db.commit()

        source.status = "transcribing"
        source.transcript_method = "whisper"
        db.commit()
        source.duration_seconds = probe_duration_seconds(dest) or episode.duration_hint
        check_duration_limit(source.duration_seconds, settings, kind="audio")
        rows = _transcribe_rows(dest, source.language, settings)
        if source.duration_seconds is None and rows:
            source.duration_seconds = float(rows[-1][1])
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
        source.progress = 100.0
        source.progress_message = "ready"
        source.error = None
        source.error_code = None
        source.error_hint = None
        db.commit()
    except Exception as exc:  # noqa: BLE001
        _fail_source(db, source_id, exc)
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
        source.error_code = None
        source.error_hint = None
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
                if p.suffix.lower() in {".mp3", ".wav", ".m4a", ".m4b", ".webm", ".ogg", ".opus", ".flac", ".aac", ".mp4", ".mkv"}
            )
            if not audio_candidates:
                raise RuntimeError("No captions and no audio available for reprocess")
            rows = _transcribe_rows(audio_candidates[0], source.language, settings)
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
        source.progress = 100.0
        source.progress_message = "ready"
        source.error = None
        source.error_code = None
        source.error_hint = None
        db.commit()
    except Exception as exc:  # noqa: BLE001
        _fail_source(db, source_id, exc)
        raise