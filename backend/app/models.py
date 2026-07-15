from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


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
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_hint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    transcript_method: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
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