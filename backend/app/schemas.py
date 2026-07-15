from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    version: str


class YouTubeCreateRequest(BaseModel):
    url: str = Field(..., min_length=8, description="YouTube video URL")
    language: str = "pl"
    auto_summarize: bool = True


class TextCreateRequest(BaseModel):
    title: str = "Untitled"
    text: str = Field(..., min_length=1)
    language: str = "pl"
    auto_summarize: bool = True


class SegmentOut(BaseModel):
    id: int
    start: float
    end: float
    text: str
    ord: int

    model_config = {"from_attributes": True}


class SummaryOut(BaseModel):
    id: int
    kind: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SourceOut(BaseModel):
    id: int
    user_id: str = "anonymous"
    source_type: str
    title: str
    url: Optional[str] = None
    video_id: Optional[str] = None
    language: str
    status: str
    error: Optional[str] = None
    error_code: Optional[str] = None
    error_hint: Optional[str] = None
    duration_seconds: Optional[float] = None
    transcript_method: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    segment_count: int = 0

    model_config = {"from_attributes": True}


class AskOut(BaseModel):
    id: int
    source_id: int
    question: str
    answer: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SourceDetailOut(SourceOut):
    segments: list[SegmentOut] = []
    summaries: list[SummaryOut] = []


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    source_id: Optional[int] = None


class Citation(BaseModel):
    start: float
    end: float
    timestamp: str
    text: str


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation] = []
    source_id: int


class SummarizeRequest(BaseModel):
    kind: str = "briefing"


class ReprocessRequest(BaseModel):
    prefer_captions: bool = True
    force_asr: bool = False
    auto_summarize: bool = True


class JobStatusOut(BaseModel):
    source_id: int
    status: str
    error: Optional[str] = None
    error_code: Optional[str] = None
    error_hint: Optional[str] = None
    progress: str = ""