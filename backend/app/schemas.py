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
    source_type: str
    title: str
    url: Optional[str] = None
    video_id: Optional[str] = None
    language: str
    status: str
    progress: float = 0.0
    progress_message: str = ""
    error: Optional[str] = None
    error_code: Optional[str] = None
    error_hint: Optional[str] = None
    duration_seconds: Optional[float] = None
    transcript_method: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    show_title: Optional[str] = None
    published_at: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    segment_count: int = 0
    share_slug: Optional[str] = None
    is_public: bool = False
    tags: list[str] = []

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
    progress_pct: float = 0.0
    progress_message: str = ""


class PlaylistCreateRequest(BaseModel):
    urls: list[str] = Field(..., min_length=1)
    language: str = "pl"
    auto_summarize: bool = True


class ShareOut(BaseModel):
    source_id: int
    share_slug: str
    share_url: str
    is_public: bool = True


class QuotaCounter(BaseModel):
    used: int
    limit: int
    remaining: int


class QuotaOut(BaseModel):
    sources: QuotaCounter
    questions: QuotaCounter
    global_llm: QuotaCounter



class ArticleCreateRequest(BaseModel):
    url: str = Field(..., min_length=8)
    title: Optional[str] = None
    language: str = "pl"
    auto_summarize: bool = True


class PodcastEpisodeCreateRequest(BaseModel):
    url: str = Field(..., min_length=8, description="Direct audio URL, episode page, or single-item feed")
    language: str = "pl"
    auto_summarize: bool = True


class PodcastRssCreateRequest(BaseModel):
    feed_url: str = Field(..., min_length=8)
    max_episodes: int = Field(default=3, ge=1, le=20)
    language: str = "pl"
    auto_summarize: bool = True



class AuthRegisterRequest(BaseModel):
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)
    turnstile_token: str = ""


class AuthLoginRequest(BaseModel):
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)


class AuthOut(BaseModel):
    email: str
    verified: bool = True


class RegisterOut(BaseModel):
    ok: bool = True
    verification_required: bool = True


class ResendVerificationRequest(BaseModel):
    email: str = Field(..., min_length=5)


class CollectionCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class CollectionOut(BaseModel):
    id: int
    name: str
    source_ids: list[int] = []

    model_config = {"from_attributes": True}


class TagOut(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class TagAssignRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)


class NoteCreateRequest(BaseModel):
    body: str = Field(..., min_length=1)


class NoteOut(BaseModel):
    id: int
    source_id: int
    body: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SearchHit(BaseModel):
    source_id: int
    title: str
    source_type: str
    snippet: str
    match_kind: str


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit] = []



class PasswordResetRequest(BaseModel):
    email: str = Field(..., min_length=5)


class PasswordResetConfirm(BaseModel):
    token: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=6)


class PasswordResetOut(BaseModel):
    ok: bool = True


class QueueStatsOut(BaseModel):
    pending: int = 0
    downloading: int = 0
    transcribing: int = 0
    summarizing: int = 0
    ready: int = 0
    failed: int = 0
    retry_scheduled: int = 0
    oldest_pending_id: Optional[int] = None
    oldest_pending_age_seconds: Optional[float] = None
