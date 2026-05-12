from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from auto_football.schemas import ContentMode, ContentStatus


class Base(DeclarativeBase):
    pass


class IngestionRunRecord(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), default="started")
    source_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    selected_match_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MatchRecord(Base):
    __tablename__ = "matches"

    match_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    league: Mapped[str] = mapped_column(String(128))
    match_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    home_logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    away_logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    competition_logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    contents: Mapped[list["ContentRecord"]] = relationship(back_populates="match")


class RawFixtureRecord(Base):
    __tablename__ = "raw_fixtures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("ingestion_runs.id"), nullable=True)
    run_date: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(32))
    fixture_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    league: Mapped[str | None] = mapped_column(String(128), nullable=True)
    home_team: Mapped[str | None] = mapped_column(String(128), nullable=True)
    away_team: Mapped[str | None] = mapped_column(String(128), nullable=True)
    match_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SelectionResultRecord(Base):
    __tablename__ = "selection_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingestion_runs.id"))
    fixture_id: Mapped[int] = mapped_column(Integer)
    selected: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[int] = mapped_column(Integer, default=0)
    reason: Mapped[str] = mapped_column(Text, default="")
    selection_meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SourceDocumentRecord(Base):
    __tablename__ = "source_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("ingestion_runs.id"), nullable=True)
    fixture_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(32))
    source_type: Mapped[str] = mapped_column(String(32), default="external")
    team_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_text: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class MergedContextRecord(Base):
    __tablename__ = "merged_contexts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("ingestion_runs.id"), nullable=True)
    fixture_id: Mapped[int] = mapped_column(Integer)
    cache_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    api_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    crawler_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    merged_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class ContentRecord(Base):
    __tablename__ = "contents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.match_id"))
    platform: Mapped[str] = mapped_column(String(32))
    publish_channel: Mapped[str] = mapped_column(String(32), default="unknown")
    mode: Mapped[str] = mapped_column(String(32), default=ContentMode.PRE_MATCH.value)
    account_id: Mapped[str] = mapped_column(String(64), default="default")
    status: Mapped[str] = mapped_column(String(32), default=ContentStatus.DRAFTED.value)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(256))
    content: Mapped[str] = mapped_column(Text)
    images: Mapped[list[str]] = mapped_column(JSON, default=list)
    remote_images: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_urls: Mapped[list[str]] = mapped_column(JSON, default=list)
    primary_media_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    editorial_style: Mapped[str | None] = mapped_column(String(64), nullable=True)
    editorial_outline: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_readiness: Mapped[str | None] = mapped_column(String(32), nullable=True)
    candidate_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    candidate_group: Mapped[str | None] = mapped_column(String(128), nullable=True)
    candidate_count: Mapped[int] = mapped_column(Integer, default=1)
    quality_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    editorial_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    match: Mapped[MatchRecord] = relationship(back_populates="contents")


class PublishLogRecord(Base):
    __tablename__ = "publish_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.match_id"))
    platform: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    publish_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class DouyinVideoTaskRecordModel(Base):
    __tablename__ = "douyin_video_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(Integer)
    video_mode: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(32), default="pixelle")
    provider_task_id: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    status: Mapped[str] = mapped_column(String(64))
    video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
