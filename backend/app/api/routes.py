from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import __version__
from app.config import get_settings
from app.db import get_db
from app.jobs import run_in_background
from app.llm.qa import answer_question
from app.llm.summarize import summarize_segments
from app.models import Source, Summary
from app.pipeline import process_text_source, process_upload_source, process_youtube_source
from app.schemas import (
    AskRequest,
    AskResponse,
    HealthResponse,
    JobStatusOut,
    SourceDetailOut,
    SourceOut,
    SummarizeRequest,
    SummaryOut,
    TextCreateRequest,
    YouTubeCreateRequest,
)

router = APIRouter()


def _to_source_out(source: Source) -> SourceOut:
    return SourceOut(
        id=source.id,
        source_type=source.source_type,
        title=source.title,
        url=source.url,
        language=source.language,
        status=source.status,
        error=source.error,
        duration_seconds=source.duration_seconds,
        transcript_method=source.transcript_method,
        created_at=source.created_at,
        updated_at=source.updated_at,
        segment_count=len(source.segments) if source.segments is not None else 0,
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)


@router.get("/sources", response_model=list[SourceOut])
def list_sources(db: Session = Depends(get_db)) -> list[SourceOut]:
    sources = db.scalars(select(Source).options(selectinload(Source.segments)).order_by(Source.id.desc())).all()
    return [_to_source_out(s) for s in sources]


@router.get("/sources/{source_id}", response_model=SourceDetailOut)
def get_source(source_id: int, db: Session = Depends(get_db)) -> SourceDetailOut:
    source = db.scalar(
        select(Source)
        .where(Source.id == source_id)
        .options(selectinload(Source.segments), selectinload(Source.summaries))
    )
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    base = _to_source_out(source)
    return SourceDetailOut(
        **base.model_dump(),
        segments=source.segments,
        summaries=source.summaries,
    )


@router.get("/sources/{source_id}/status", response_model=JobStatusOut)
def get_status(source_id: int, db: Session = Depends(get_db)) -> JobStatusOut:
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    progress_map = {
        "pending": "Queued",
        "downloading": "Downloading media",
        "transcribing": "Transcribing / extracting text",
        "summarizing": "Generating summary",
        "ready": "Ready",
        "failed": "Failed",
    }
    return JobStatusOut(
        source_id=source.id,
        status=source.status,
        error=source.error,
        progress=progress_map.get(source.status, source.status),
    )


@router.post("/sources/youtube", response_model=SourceOut)
def create_youtube_source(
    payload: YouTubeCreateRequest,
    db: Session = Depends(get_db),
) -> SourceOut:
    source = Source(
        source_type="youtube",
        title="YouTube video",
        url=payload.url,
        language=payload.language,
        status="pending",
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    run_in_background(process_youtube_source, source.id, auto_summarize=payload.auto_summarize)
    source = db.scalar(select(Source).where(Source.id == source.id).options(selectinload(Source.segments)))
    assert source is not None
    return _to_source_out(source)


@router.post("/sources/text", response_model=SourceOut)
def create_text_source(
    payload: TextCreateRequest,
    db: Session = Depends(get_db),
) -> SourceOut:
    source = Source(
        source_type="text",
        title=payload.title,
        language=payload.language,
        status="pending",
        transcript_method="text",
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    run_in_background(
        process_text_source,
        source.id,
        text=payload.text,
        auto_summarize=payload.auto_summarize,
    )
    source = db.scalar(select(Source).where(Source.id == source.id).options(selectinload(Source.segments)))
    assert source is not None
    return _to_source_out(source)


@router.post("/sources/upload", response_model=SourceOut)
async def upload_source(
    file: UploadFile = File(...),
    language: str = Form("pl"),
    title: Optional[str] = Form(None),
    auto_summarize: bool = Form(True),
    db: Session = Depends(get_db),
) -> SourceOut:
    settings = get_settings()
    original_name = file.filename or "upload.bin"
    suffix = Path(original_name).suffix.lower()
    if suffix not in {".pdf", ".txt", ".md", ".mp3", ".wav", ".m4a", ".webm", ".ogg", ".mp4", ".mkv"}:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")

    source_type = "pdf" if suffix == ".pdf" else "audio" if suffix in {".mp3", ".wav", ".m4a", ".webm", ".ogg", ".mp4", ".mkv"} else "text"
    source = Source(
        source_type=source_type,
        title=title or original_name,
        language=language,
        status="pending",
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    dest_dir = settings.media_dir / f"source_{source.id}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / original_name
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    source.file_path = str(dest)
    db.commit()

    run_in_background(process_upload_source, source.id, auto_summarize=auto_summarize)
    source = db.scalar(select(Source).where(Source.id == source.id).options(selectinload(Source.segments)))
    assert source is not None
    return _to_source_out(source)


@router.post("/sources/{source_id}/summarize", response_model=SummaryOut)
def summarize_source(
    source_id: int,
    payload: SummarizeRequest,
    db: Session = Depends(get_db),
) -> SummaryOut:
    source = db.scalar(
        select(Source).where(Source.id == source_id).options(selectinload(Source.segments))
    )
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    if source.status != "ready":
        raise HTTPException(status_code=409, detail=f"Source not ready (status={source.status})")

    segs = [(s.start, s.end, s.text) for s in source.segments]
    content = summarize_segments(segs, title=source.title, kind=payload.kind)
    summary = Summary(source_id=source.id, kind=payload.kind, content=content)
    db.add(summary)
    db.commit()
    db.refresh(summary)
    return summary


@router.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest, db: Session = Depends(get_db)) -> AskResponse:
    if payload.source_id is None:
        raise HTTPException(status_code=400, detail="source_id is required")
    source = db.scalar(
        select(Source).where(Source.id == payload.source_id).options(selectinload(Source.segments))
    )
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    if source.status != "ready":
        raise HTTPException(status_code=409, detail=f"Source not ready (status={source.status})")

    segs = [(s.start, s.end, s.text) for s in source.segments]
    answer, citations = answer_question(payload.question, segs, title=source.title)
    return AskResponse(answer=answer, citations=citations, source_id=source.id)


@router.delete("/sources/{source_id}")
def delete_source(source_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    settings = get_settings()
    media_dir = settings.media_dir / f"source_{source.id}"
    db.delete(source)
    db.commit()
    if media_dir.exists():
        shutil.rmtree(media_dir, ignore_errors=True)
    return {"status": "deleted"}