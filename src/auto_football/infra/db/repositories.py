from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import delete, select, text

from auto_football.schemas import (
    DouyinVideoTaskRecord,
    DouyinVideoTaskStatus,
    GeneratedContent,
    MatchInfo,
    MergedMatchContext,
    PublishResult,
    SelectionDecision,
    SourceDocument,
)

from .models import (
    ContentRecord,
    DouyinVideoTaskRecordModel,
    IngestionRunRecord,
    MatchRecord,
    MergedContextRecord,
    PublishLogRecord,
    RawFixtureRecord,
    SelectionResultRecord,
    SourceDocumentRecord,
)


def create_run(session, run_date: date) -> int:
    record = IngestionRunRecord(run_date=run_date, status="started")
    session.add(record)
    session.commit()
    return record.id


def complete_run(session, run_id: int, *, selected_match_ids: list[int], source_summary: dict[str, Any]) -> None:
    run = session.get(IngestionRunRecord, run_id)
    if run is None:
        return
    run.status = "completed"
    run.selected_match_ids = selected_match_ids
    run.source_summary = source_summary
    run.completed_at = datetime.utcnow()
    session.commit()


def save_raw_fixtures(session, fixture_id_fn, fixture_league_fn, fixture_home_fn, fixture_away_fn, fixture_match_time_fn, run_id: int, run_date: date, source: str, fixtures: list[dict[str, Any]]) -> None:
    rows: list[RawFixtureRecord] = []
    for fixture in fixtures:
        rows.append(
            RawFixtureRecord(
                run_id=run_id,
                run_date=run_date,
                source=source,
                fixture_id=fixture_id_fn(fixture),
                league=fixture_league_fn(fixture),
                home_team=fixture_home_fn(fixture),
                away_team=fixture_away_fn(fixture),
                match_time=fixture_match_time_fn(fixture),
                payload=fixture,
            )
        )
    session.add_all(rows)
    session.commit()


def save_selection_results(session, run_id: int, decisions: list[SelectionDecision]) -> None:
    session.add_all(
        [
            SelectionResultRecord(
                run_id=run_id,
                fixture_id=item.fixture_id,
                selected=item.selected,
                score=item.score,
                reason=item.reason,
                selection_meta=item.metadata,
            )
            for item in decisions
        ]
    )
    session.commit()


def save_source_documents(session, run_id: int, fixture_id: int, documents: list[SourceDocument]) -> None:
    if not documents:
        return
    session.add_all(
        [
            SourceDocumentRecord(
                run_id=run_id,
                fixture_id=fixture_id,
                source=item.source,
                source_type=item.source_type,
                team_name=item.team_name,
                url=item.url,
                title=item.title,
                published_at=item.published_at,
                crawled_at=item.crawled_at,
                summary=item.summary,
                content_text=item.content_text,
                payload=item.payload,
            )
            for item in documents
        ]
    )
    session.commit()


def save_merged_context(session, run_id: int, context: MergedMatchContext) -> None:
    session.add(
        MergedContextRecord(
            run_id=run_id,
            fixture_id=context.fixture_id,
            cache_key=context.cache_key,
            api_snapshot=context.api_snapshot,
            crawler_snapshot=[item.model_dump(mode="json") for item in context.crawler_documents],
            merged_payload=context.merged_payload,
        )
    )
    session.commit()


def upsert_match(session, data: MatchInfo) -> None:
    record = session.get(MatchRecord, data.match_id)
    if record is None:
        record = MatchRecord(match_id=data.match_id)
        session.add(record)
    record.league = data.league
    record.match_time = data.match_time
    record.status = "ready" if data.must_fill else "incomplete"
    session.flush()
    session.execute(
        text(
            """
            update matches
            set home_team = :home_team,
                away_team = :away_team,
                home_logo_url = :home_logo_url,
                away_logo_url = :away_logo_url,
                competition_logo_url = :competition_logo_url,
                fixture_status = :fixture_status,
                fixture_status_text = :fixture_status_text,
                home_rank = :home_rank,
                away_rank = :away_rank,
                home_recent_form = :home_recent_form,
                away_recent_form = :away_recent_form,
                injuries = :injuries,
                odds_payload = :odds_payload,
                rank_source = :rank_source,
                form_source = :form_source,
                standings_summary = :standings_summary,
                form_summary = :form_summary,
                home_score = :home_score,
                away_score = :away_score,
                home_elo = :home_elo,
                away_elo = :away_elo,
                home_elo_rank = :home_elo_rank,
                away_elo_rank = :away_elo_rank,
                knowledge_briefs = :knowledge_briefs,
                source_documents_count = :source_documents_count,
                merged_context_payload = :merged_context_payload,
                updated_at = :updated_at
            where match_id = :match_id
            """
        ),
        {
            "match_id": data.match_id,
            "home_team": data.home_team,
            "away_team": data.away_team,
            "home_logo_url": data.home_logo_url,
            "away_logo_url": data.away_logo_url,
            "competition_logo_url": data.competition_logo_url,
            "fixture_status": data.fixture_status,
            "fixture_status_text": data.fixture_status_text,
            "home_rank": data.home_rank,
            "away_rank": data.away_rank,
            "home_recent_form": json.dumps(data.home_recent_form, ensure_ascii=False),
            "away_recent_form": json.dumps(data.away_recent_form, ensure_ascii=False),
            "injuries": json.dumps(data.injuries or [], ensure_ascii=False),
            "odds_payload": json.dumps(data.odds or {}, ensure_ascii=False),
            "rank_source": data.rank_source,
            "form_source": data.form_source,
            "standings_summary": data.standings_summary,
            "form_summary": data.form_summary,
            "home_score": data.home_score,
            "away_score": data.away_score,
            "home_elo": data.home_elo,
            "away_elo": data.away_elo,
            "home_elo_rank": data.home_elo_rank,
            "away_elo_rank": data.away_elo_rank,
            "knowledge_briefs": json.dumps(data.knowledge_briefs, ensure_ascii=False),
            "source_documents_count": data.source_documents_count,
            "merged_context_payload": json.dumps(data.merged_context or {}, ensure_ascii=False),
            "updated_at": datetime.utcnow(),
        },
    )
    session.commit()


def save_content(session, primary_media_path_fn, match_id: int | GeneratedContent, payload: GeneratedContent | None = None) -> None:
    content = match_id if isinstance(match_id, GeneratedContent) else payload
    if content is None:
        raise ValueError("GeneratedContent payload is required.")
    save_contents(session, primary_media_path_fn, [content], match_id=match_id if isinstance(match_id, int) else None)


def save_contents(
    session,
    primary_media_path_fn,
    contents: list[GeneratedContent],
    *,
    match_id: int | None = None,
) -> None:
    if not contents:
        return

    resolved_matches: dict[int, MatchRecord] = {}
    slice_keys: set[tuple[int, str, str, str]] = set()

    for content in contents:
        resolved_match_id = content.match_id or match_id or 0
        if not resolved_match_id:
            raise ValueError("Match ID is required for content persistence.")

        match = session.get(MatchRecord, resolved_match_id)
        if match is None:
            raise ValueError(f"Match {resolved_match_id} not found. Run enrichment first.")
        resolved_matches[resolved_match_id] = match
        slice_keys.add((resolved_match_id, content.platform.value, content.mode.value, content.account_id))

    for resolved_match_id, platform, mode, account_id in slice_keys:
        session.execute(
            delete(ContentRecord).where(
                ContentRecord.match_id == resolved_match_id,
                ContentRecord.platform == platform,
                ContentRecord.mode == mode,
                ContentRecord.account_id == account_id,
            )
        )

    session.flush()

    for content in contents:
        resolved_match_id = content.match_id or match_id or 0
        existing = _find_existing_content_record(session, resolved_match_id, content)
        if existing is None:
            existing = ContentRecord(
                match_id=resolved_match_id,
                platform=content.platform.value,
                publish_channel=content.platform.value,
                mode=content.mode.value,
                account_id=content.account_id,
                title="",
                content="",
            )
            session.add(existing)

        _apply_content_to_record(existing, primary_media_path_fn, content, resolved_match_id)
        resolved_matches[resolved_match_id].updated_at = datetime.utcnow()

    session.commit()


def clear_content_slice(session, match_id: int, platform: str, mode: str, account_id: str) -> None:
    session.execute(
        delete(ContentRecord).where(
            ContentRecord.match_id == match_id,
            ContentRecord.platform == platform,
            ContentRecord.mode == mode,
            ContentRecord.account_id == account_id,
        )
    )
    session.commit()


def update_content_assets(session, primary_media_path_fn, content: GeneratedContent) -> None:
    match_id = content.match_id or 0
    if not match_id:
        raise ValueError("Match ID is required for content asset updates.")

    existing = _find_existing_content_record(session, match_id, content)
    if existing is None:
        raise ValueError("Target content record not found for asset update.")

    existing.images = content.images
    existing.remote_images = content.remote_images
    existing.primary_media_path = content.primary_media_path or primary_media_path_fn(content)
    existing.editorial_metadata = {
        **(existing.editorial_metadata or {}),
        **(content.editorial_metadata or {}),
    }
    session.commit()


def clone_content_assets_to_slice(session, primary_media_path_fn, content: GeneratedContent) -> None:
    match_id = content.match_id or 0
    if not match_id:
        raise ValueError("Match ID is required for content asset cloning.")

    rows = session.execute(
        select(ContentRecord).where(
            ContentRecord.match_id == match_id,
            ContentRecord.platform == content.platform.value,
            ContentRecord.mode == content.mode.value,
            ContentRecord.account_id == content.account_id,
        )
    ).scalars().all()
    for row in rows:
        row.images = content.images
        row.remote_images = content.remote_images
        row.primary_media_path = content.primary_media_path or primary_media_path_fn(content)
    session.commit()


def get_latest_context_snapshot(session, fixture_id: int) -> dict[str, Any] | None:
    context = session.execute(
        select(MergedContextRecord)
        .where(MergedContextRecord.fixture_id == fixture_id)
        .order_by(MergedContextRecord.created_at.desc(), MergedContextRecord.id.desc())
    ).scalars().first()
    if context is None:
        return None
    documents = session.execute(
        select(SourceDocumentRecord)
        .where(SourceDocumentRecord.fixture_id == fixture_id)
        .order_by(SourceDocumentRecord.created_at.desc(), SourceDocumentRecord.id.desc())
    ).scalars().all()
    return {
        "fixture_id": fixture_id,
        "cache_key": context.cache_key,
        "api_snapshot": context.api_snapshot or {},
        "merged_payload": context.merged_payload or {},
        "source_documents": [
            {
                "source": item.source,
                "source_type": item.source_type,
                "team_name": item.team_name,
                "url": item.url,
                "title": item.title,
                "summary": item.summary,
                "content_text": item.content_text,
                "payload": item.payload or {},
                "published_at": item.published_at,
                "crawled_at": item.crawled_at,
            }
            for item in documents
        ],
    }


def _find_existing_content_record(session, match_id: int, content: GeneratedContent) -> ContentRecord | None:
    candidate_group = content.candidate_group
    candidate_rank = content.candidate_rank
    if candidate_group and candidate_rank is not None:
        return session.execute(
            select(ContentRecord).where(
                ContentRecord.match_id == match_id,
                ContentRecord.platform == content.platform.value,
                ContentRecord.mode == content.mode.value,
                ContentRecord.account_id == content.account_id,
                ContentRecord.candidate_group == candidate_group,
                ContentRecord.candidate_rank == candidate_rank,
            )
        ).scalar_one_or_none()

    if candidate_rank is not None:
        return session.execute(
            select(ContentRecord).where(
                ContentRecord.match_id == match_id,
                ContentRecord.platform == content.platform.value,
                ContentRecord.mode == content.mode.value,
                ContentRecord.account_id == content.account_id,
                ContentRecord.candidate_rank == candidate_rank,
            )
        ).scalar_one_or_none()

    return session.execute(
        select(ContentRecord).where(
            ContentRecord.match_id == match_id,
            ContentRecord.platform == content.platform.value,
            ContentRecord.mode == content.mode.value,
            ContentRecord.account_id == content.account_id,
            ContentRecord.candidate_rank.is_(None),
        )
    ).scalar_one_or_none()


def _apply_content_to_record(
    record: ContentRecord,
    primary_media_path_fn,
    content: GeneratedContent,
    match_id: int,
) -> None:
    record.match_id = match_id
    record.platform = content.platform.value
    record.publish_channel = content.platform.value
    record.mode = content.mode.value
    record.account_id = content.account_id
    record.status = content.status.value
    record.priority = content.priority
    record.title = content.title
    record.content = content.content
    record.images = content.images
    record.remote_images = content.remote_images
    record.source_urls = content.source_urls
    record.primary_media_path = content.primary_media_path or primary_media_path_fn(content)
    record.tags = content.tags or []
    record.editorial_style = content.editorial_style.value if content.editorial_style else None
    record.editorial_outline = content.editorial_outline.value if content.editorial_outline else None
    record.content_readiness = content.content_readiness.value if content.content_readiness else None
    record.candidate_rank = content.candidate_rank
    record.candidate_group = content.candidate_group
    record.candidate_count = content.candidate_count or 1
    record.quality_summary = content.quality_summary
    record.editorial_metadata = content.editorial_metadata or {}


def log_publish(session, match_id: int, payload: PublishResult) -> None:
    session.add(
        PublishLogRecord(
            match_id=match_id,
            platform=payload.platform.value,
            status=payload.status,
            publish_id=payload.publish_id,
            error_message=payload.error_message,
        )
    )
    session.commit()


def save_douyin_video_task(session, payload: DouyinVideoTaskRecord) -> DouyinVideoTaskRecord:
    record = DouyinVideoTaskRecordModel(
        match_id=payload.match_id,
        video_mode=payload.video_mode.value,
        provider=payload.provider,
        provider_task_id=payload.provider_task_id,
        status=payload.status.value,
        video_url=payload.video_url,
        error_message=payload.error_message,
        payload_snapshot=payload.payload_snapshot,
    )
    session.add(record)
    session.commit()
    return payload


def get_douyin_video_task(session, provider_task_id: str) -> DouyinVideoTaskRecord | None:
    row = session.execute(
        select(DouyinVideoTaskRecordModel).where(DouyinVideoTaskRecordModel.provider_task_id == provider_task_id)
    ).scalar_one_or_none()
    if row is None:
        return None
    return DouyinVideoTaskRecord(
        match_id=row.match_id,
        video_mode=row.video_mode,
        provider=row.provider,
        provider_task_id=row.provider_task_id,
        status=row.status,
        video_url=row.video_url,
        error_message=row.error_message,
        payload_snapshot=row.payload_snapshot or {},
    )


def update_douyin_video_task(
    session,
    provider_task_id: str,
    *,
    status: DouyinVideoTaskStatus,
    video_url: str | None,
    error_message: str | None,
) -> DouyinVideoTaskRecord:
    row = session.execute(
        select(DouyinVideoTaskRecordModel).where(DouyinVideoTaskRecordModel.provider_task_id == provider_task_id)
    ).scalar_one()
    row.status = status.value
    row.video_url = video_url
    row.error_message = error_message
    row.updated_at = datetime.utcnow()
    session.commit()
    return DouyinVideoTaskRecord(
        match_id=row.match_id,
        video_mode=row.video_mode,
        provider=row.provider,
        provider_task_id=row.provider_task_id,
        status=row.status,
        video_url=row.video_url,
        error_message=row.error_message,
        payload_snapshot=row.payload_snapshot or {},
    )
