from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), default="")
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_token_hash: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True, index=True)
    verification_token_expires: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reset_token: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True, index=True)
    reset_token_expires: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RateLimitEvent(Base):
    __tablename__ = "rate_limit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bucket: Mapped[str] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"), nullable=True, index=True)
    units: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), default="anonymous", index=True)
    source_type: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(512), default="")
    url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    video_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    language: Mapped[str] = mapped_column(String(16), default="pl")
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    progress_message: Mapped[str] = mapped_column(String(255), default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_hint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    transcript_method: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    share_slug: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True, index=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    show_title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    published_at: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    segments: Mapped[list[Segment]] = relationship(
        "Segment",
        back_populates="source",
        cascade="all, delete-orphan",
        order_by="Segment.start",
    )
    summaries: Mapped[list[Summary]] = relationship(
        "Summary",
        back_populates="source",
        cascade="all, delete-orphan",
    )
    asks: Mapped[list["Ask"]] = relationship(
        "Ask",
        back_populates="source",
        cascade="all, delete-orphan",
        order_by="Ask.created_at",
    )
    notes: Mapped[list["Note"]] = relationship(
        "Note",
        back_populates="source",
        cascade="all, delete-orphan",
        order_by="Note.created_at",
    )
    tags: Mapped[list["Tag"]] = relationship(
        "Tag",
        secondary="source_tags",
        back_populates="sources",
    )
    collections: Mapped[list["Collection"]] = relationship(
        "Collection",
        secondary="collection_sources",
        back_populates="sources",
    )


class Segment(Base):
    __tablename__ = "segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    start: Mapped[float] = mapped_column(Float, default=0.0)
    end: Mapped[float] = mapped_column(Float, default=0.0)
    text: Mapped[str] = mapped_column(Text, default="")
    ord: Mapped[int] = mapped_column(Integer, default=0)

    source: Mapped[Source] = relationship("Source", back_populates="segments")


class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(64), default="briefing")
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source: Mapped[Source] = relationship("Source", back_populates="summaries")


class Ask(Base):
    __tablename__ = "asks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    question: Mapped[str] = mapped_column(Text, default="")
    answer: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source: Mapped[Source] = relationship("Source", back_populates="asks")


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sources: Mapped[list[Source]] = relationship(
        "Source",
        secondary="collection_sources",
        back_populates="collections",
    )


class CollectionSource(Base):
    __tablename__ = "collection_sources"
    __table_args__ = (UniqueConstraint("collection_id", "source_id", name="uq_collection_source"),)

    collection_id: Mapped[int] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True
    )
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True)


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_user_tag"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(64), default="")

    sources: Mapped[list[Source]] = relationship(
        "Source",
        secondary="source_tags",
        back_populates="tags",
    )


class SourceTag(Base):
    __tablename__ = "source_tags"
    __table_args__ = (UniqueConstraint("source_id", "tag_id", name="uq_source_tag"),)

    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    body: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source: Mapped[Source] = relationship("Source", back_populates="notes")
