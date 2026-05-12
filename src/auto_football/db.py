from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from auto_football.config import Settings
from auto_football.schemas import (
    ContentMode,
    ContentStatus,
    DouyinVideoTaskRecord,
    GeneratedContent,
    MatchInfo,
    MergedMatchContext,
    Platform,
    PublishResult,
    SelectionDecision,
    SourceDocument,
)
from auto_football.infra.db.migrations import (
    ensure_content_columns,
    ensure_douyin_video_task_columns,
    ensure_match_columns,
    migrate_content_status_values,
)
from auto_football.infra.db.models import (
    Base,
    ContentRecord,
    IngestionRunRecord,
    MatchRecord,
    MergedContextRecord,
    PublishLogRecord,
    RawFixtureRecord,
    SelectionResultRecord,
    SourceDocumentRecord,
)
from auto_football.infra.db.preview_queries import build_match_bundle, build_preview_payloads
from auto_football.infra.db import repositories


class Database:
    def __init__(self, settings: Settings) -> None:
        self.engine = create_engine(settings.database_url, future=True)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)

    def init_db(self) -> None:
        Base.metadata.create_all(self.engine)
        ensure_match_columns(self.engine)
        ensure_content_columns(self.engine)
        ensure_douyin_video_task_columns(self.engine)
        migrate_content_status_values(self.engine)

    def session(self) -> Session:
        return self.session_factory()

    def create_run(self, run_date: date) -> int:
        with self.session() as session:
            return repositories.create_run(session, run_date)

    def complete_run(self, run_id: int, *, selected_match_ids: list[int], source_summary: dict[str, Any]) -> None:
        with self.session() as session:
            repositories.complete_run(session, run_id, selected_match_ids=selected_match_ids, source_summary=source_summary)

    def save_raw_fixtures(self, run_id: int, run_date: date, source: str, fixtures: list[dict[str, Any]]) -> None:
        with self.session() as session:
            repositories.save_raw_fixtures(
                session,
                self._fixture_id,
                self._fixture_league,
                self._fixture_home_team,
                self._fixture_away_team,
                self._fixture_match_time,
                run_id,
                run_date,
                source,
                fixtures,
            )

    def save_selection_results(self, run_id: int, decisions: list[SelectionDecision]) -> None:
        with self.session() as session:
            repositories.save_selection_results(session, run_id, decisions)

    def save_source_documents(self, run_id: int, fixture_id: int, documents: list[SourceDocument]) -> None:
        with self.session() as session:
            repositories.save_source_documents(session, run_id, fixture_id, documents)

    def save_merged_context(self, run_id: int, context: MergedMatchContext) -> None:
        with self.session() as session:
            repositories.save_merged_context(session, run_id, context)

    def upsert_match(self, data: MatchInfo) -> None:
        with self.session() as session:
            repositories.upsert_match(session, data)

    def save_content(self, match_id: int | GeneratedContent, payload: GeneratedContent | None = None) -> None:
        with self.session() as session:
            repositories.save_content(session, self._primary_media_path, match_id, payload)

    def save_contents(self, contents: list[GeneratedContent], *, match_id: int | None = None) -> None:
        with self.session() as session:
            repositories.save_contents(session, self._primary_media_path, contents, match_id=match_id)

    def update_content_assets(self, content: GeneratedContent) -> None:
        with self.session() as session:
            repositories.update_content_assets(session, self._primary_media_path, content)

    def clone_content_assets_to_slice(self, content: GeneratedContent) -> None:
        with self.session() as session:
            repositories.clone_content_assets_to_slice(session, self._primary_media_path, content)

    def clear_content_slice(self, *, match_id: int, platform: Platform, mode: ContentMode, account_id: str) -> None:
        with self.session() as session:
            repositories.clear_content_slice(session, match_id, platform.value, mode.value, account_id)

    def log_publish(self, match_id: int, payload: PublishResult) -> None:
        with self.session() as session:
            repositories.log_publish(session, match_id, payload)

    def get_preview_payloads(
        self,
        *,
        match_id: int | None = None,
        limit_matches: int = 3,
        reference_time: datetime | None = None,
    ) -> list[dict[str, Any]]:
        with self.session() as session:
            return build_preview_payloads(
                session,
                self._json_loads,
                match_id=match_id,
                limit_matches=limit_matches,
                reference_time=reference_time,
            )

    def get_match_bundle(self, match_id: int) -> dict[str, Any] | None:
        with self.session() as session:
            return build_match_bundle(session, self._json_loads, match_id)

    def get_latest_context_snapshot(self, fixture_id: int) -> dict[str, Any] | None:
        with self.session() as session:
            return repositories.get_latest_context_snapshot(session, fixture_id)

    def save_douyin_video_task(self, payload: DouyinVideoTaskRecord) -> DouyinVideoTaskRecord:
        with self.session() as session:
            return repositories.save_douyin_video_task(session, payload)

    def get_douyin_video_task(self, provider_task_id: str) -> DouyinVideoTaskRecord | None:
        with self.session() as session:
            return repositories.get_douyin_video_task(session, provider_task_id)

    def update_douyin_video_task(
        self,
        provider_task_id: str,
        *,
        status,
        video_url: str | None = None,
        error_message: str | None = None,
    ) -> DouyinVideoTaskRecord:
        with self.session() as session:
            return repositories.update_douyin_video_task(
                session,
                provider_task_id,
                status=status,
                video_url=video_url,
                error_message=error_message,
            )

    @staticmethod
    def _fixture_id(fixture: dict[str, Any]) -> int | None:
        if "fixture" in fixture:
            return fixture.get("fixture", {}).get("id")
        return fixture.get("id")

    @staticmethod
    def _fixture_league(fixture: dict[str, Any]) -> str | None:
        if "league" in fixture:
            return fixture.get("league", {}).get("name")
        return fixture.get("competition_name_en") or fixture.get("competition_name_zh")

    @staticmethod
    def _fixture_home_team(fixture: dict[str, Any]) -> str | None:
        if "teams" in fixture:
            return fixture.get("teams", {}).get("home", {}).get("name")
        return fixture.get("home_team_name_en") or fixture.get("home_team_name_zh")

    @staticmethod
    def _fixture_away_team(fixture: dict[str, Any]) -> str | None:
        if "teams" in fixture:
            return fixture.get("teams", {}).get("away", {}).get("name")
        return fixture.get("away_team_name_en") or fixture.get("away_team_name_zh")

    @staticmethod
    def _fixture_match_time(fixture: dict[str, Any]) -> datetime | None:
        try:
            if "fixture" in fixture:
                raw = fixture.get("fixture", {}).get("date")
                return datetime.fromisoformat(raw.replace("Z", "+00:00")) if raw else None
            raw = fixture.get("time")
            return datetime.fromtimestamp(int(raw), tz=datetime.now().astimezone().tzinfo) if raw else None
        except Exception:
            return None

    @staticmethod
    def _json_loads(value: Any) -> Any:
        if value in (None, ""):
            return [] if value == "" else None
        if isinstance(value, (list, dict)):
            return value
        try:
            return json.loads(value)
        except Exception:
            return value

    @staticmethod
    def _primary_media_path(content: GeneratedContent) -> str | None:
        if content.images:
            return content.images[0]
        if content.remote_images:
            return content.remote_images[0]
        return None
