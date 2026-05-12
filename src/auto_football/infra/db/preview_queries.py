from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, text

from auto_football.schemas import (
    ContentMode,
    ContentReadiness,
    ContentStatus,
    GeneratedContent,
    MatchInfo,
    OutlineSelection,
    Platform,
    StyleSelection,
)

from .models import ContentRecord, MatchRecord


def _content_sort_key(item: ContentRecord) -> tuple[int, int, int, datetime, str]:
    candidate_rank = item.candidate_rank if item.candidate_rank is not None else 10_000
    top_candidate_bias = 0 if candidate_rank == 1 else 1
    return (
        top_candidate_bias,
        candidate_rank,
        -item.priority,
        item.created_at,
        item.account_id,
    )


def _record_to_generated_content(match_id: int, row: ContentRecord) -> GeneratedContent:
    return GeneratedContent(
        match_id=match_id,
        platform=Platform(row.platform),
        mode=ContentMode(row.mode),
        account_id=row.account_id,
        status=ContentStatus(row.status),
        priority=row.priority,
        title=row.title,
        content=row.content,
        images=row.images or [],
        remote_images=row.remote_images or [],
        source_urls=row.source_urls or [],
        primary_media_path=row.primary_media_path,
        tags=row.tags or [],
        editorial_style=StyleSelection(row.editorial_style) if row.editorial_style else None,
        editorial_outline=OutlineSelection(row.editorial_outline) if row.editorial_outline else None,
        content_readiness=ContentReadiness(row.content_readiness) if row.content_readiness else None,
        candidate_rank=row.candidate_rank,
        candidate_group=row.candidate_group,
        candidate_count=row.candidate_count or 1,
        quality_summary=row.quality_summary,
        editorial_metadata=row.editorial_metadata or {},
    )


def _grouped_candidates(rows: list[ContentRecord], match_id: int) -> tuple[dict[str, GeneratedContent], dict[str, list[GeneratedContent]]]:
    grouped_rows: dict[str, list[ContentRecord]] = {}
    for row in rows:
        grouped_rows.setdefault(row.platform, []).append(row)

    top_contents: dict[str, GeneratedContent] = {}
    content_candidates: dict[str, list[GeneratedContent]] = {}
    for platform, platform_rows in grouped_rows.items():
        # `contents` intentionally exposes one default candidate per platform for
        # callers that need a single publishable draft, while
        # `content_candidates` preserves the full same-platform candidate pool.
        ranked_rows = sorted(platform_rows, key=_content_sort_key)
        top_contents[platform] = _record_to_generated_content(match_id, ranked_rows[0])
        content_candidates[platform] = [
            _record_to_generated_content(match_id, row)
            for row in _sort_platform_candidates(platform_rows)
        ]
    return top_contents, content_candidates


def _sort_platform_candidates(rows: list[ContentRecord]) -> list[ContentRecord]:
    return sorted(rows, key=_platform_candidate_sort_key)


def _platform_candidate_sort_key(item: ContentRecord) -> tuple[int, str, str, int, int, datetime]:
    candidate_rank = item.candidate_rank if item.candidate_rank is not None else 10_000
    return (
        candidate_rank,
        item.mode,
        item.account_id,
        -item.priority,
        item.id or 0,
        item.created_at,
    )


def build_preview_payloads(
    session,
    json_loads,
    *,
    match_id: int | None = None,
    limit_matches: int = 3,
    reference_time: datetime | None = None,
) -> list[dict[str, Any]]:
    now = reference_time or datetime.now(timezone.utc)
    current_cutoff = now - timedelta(days=45)
    match_query = select(MatchRecord).order_by(MatchRecord.updated_at.desc(), MatchRecord.match_id.desc())
    if match_id is not None:
        match_query = match_query.where(MatchRecord.match_id == match_id)
    else:
        current_matches = session.execute(
            match_query.where(MatchRecord.match_time >= current_cutoff).limit(limit_matches)
        ).scalars().all()
        if current_matches:
            matches = current_matches
        else:
            matches = session.execute(match_query.limit(limit_matches)).scalars().all()
    if match_id is not None:
        matches = session.execute(match_query).scalars().all()
    payloads: list[dict[str, Any]] = []
    for match in matches:
        extra = session.execute(
            text(
                """
                select home_team, away_team, home_logo_url, away_logo_url, competition_logo_url,
                       fixture_status, fixture_status_text, home_rank, away_rank,
                       home_recent_form, away_recent_form, injuries, odds_payload,
                       rank_source, form_source, standings_summary, form_summary,
                       home_score, away_score,
                       home_elo, away_elo, home_elo_rank, away_elo_rank, knowledge_briefs,
                       source_documents_count, merged_context_payload
                from matches
                where match_id = :match_id
                """
            ),
            {"match_id": match.match_id},
        ).mappings().first()
        contents = session.execute(
            select(ContentRecord)
            .where(ContentRecord.match_id == match.match_id)
            .order_by(
                ContentRecord.platform.asc(),
                ContentRecord.priority.desc(),
                ContentRecord.created_at.desc(),
            )
        ).scalars().all()
        contents = sorted(contents, key=lambda item: (item.platform, *_content_sort_key(item)))
        match_time = _coerce_utc(match.match_time)
        is_historical_sample = bool(match_time and match_time < current_cutoff)
        payloads.append(
            {
                "match_id": match.match_id,
                "league": match.league,
                "match_time": match_time,
                "is_historical_sample": is_historical_sample,
                "workflow_status": match.status,
                "home_team": extra["home_team"] if extra else None,
                "away_team": extra["away_team"] if extra else None,
                "home_logo_url": extra["home_logo_url"] if extra else None,
                "away_logo_url": extra["away_logo_url"] if extra else None,
                "competition_logo_url": extra["competition_logo_url"] if extra else None,
                "fixture_status": extra["fixture_status"] if extra else None,
                "fixture_status_text": extra["fixture_status_text"] if extra else None,
                "home_rank": extra["home_rank"] if extra else None,
                "away_rank": extra["away_rank"] if extra else None,
                "home_recent_form": json_loads(extra["home_recent_form"]) if extra else [],
                "away_recent_form": json_loads(extra["away_recent_form"]) if extra else [],
                "injuries": json_loads(extra["injuries"]) if extra else [],
                "odds_payload": json_loads(extra["odds_payload"]) if extra else {},
                "rank_source": extra["rank_source"] if extra else None,
                "form_source": extra["form_source"] if extra else None,
                "standings_summary": extra["standings_summary"] if extra else None,
                "form_summary": extra["form_summary"] if extra else None,
                "home_score": extra["home_score"] if extra else None,
                "away_score": extra["away_score"] if extra else None,
                "home_elo": extra["home_elo"] if extra else None,
                "away_elo": extra["away_elo"] if extra else None,
                "home_elo_rank": extra["home_elo_rank"] if extra else None,
                "away_elo_rank": extra["away_elo_rank"] if extra else None,
                "knowledge_briefs": json_loads(extra["knowledge_briefs"]) if extra else [],
                "source_documents_count": extra["source_documents_count"] if extra else 0,
                "merged_context_payload": json_loads(extra["merged_context_payload"]) if extra else {},
                "coverage": (json_loads(extra["merged_context_payload"]) or {}).get("coverage", {}) if extra else {},
                "contents": [
                    {
                        "platform": item.platform,
                        "publish_channel": item.publish_channel,
                        "mode": item.mode,
                        "account_id": item.account_id,
                        "status": item.status,
                        "priority": item.priority,
                        "title": item.title,
                        "content": item.content,
                        "images": item.images or [],
                        "remote_images": item.remote_images or [],
                        "source_urls": item.source_urls or [],
                        "primary_media_path": item.primary_media_path,
                        "tags": item.tags or [],
                        "editorial_style": item.editorial_style,
                        "editorial_outline": item.editorial_outline,
                        "content_readiness": item.content_readiness,
                        "candidate_rank": item.candidate_rank,
                        "candidate_group": item.candidate_group,
                        "candidate_count": item.candidate_count or 1,
                        "quality_summary": item.quality_summary,
                        "editorial_metadata": item.editorial_metadata or {},
                        "created_at": item.created_at,
                    }
                    for item in contents
                ],
            }
        )
    return payloads


def _coerce_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def build_match_bundle(session, json_loads, match_id: int) -> dict[str, Any] | None:
    match = session.get(MatchRecord, match_id)
    if match is None:
        return None
    extra = session.execute(
        text(
            """
            select home_team, away_team, home_logo_url, away_logo_url, competition_logo_url,
                   fixture_status, fixture_status_text, home_rank, away_rank,
                   home_recent_form, away_recent_form, injuries, odds_payload,
                   rank_source, form_source, standings_summary, form_summary,
                   home_score, away_score,
                   home_elo, away_elo, home_elo_rank, away_elo_rank, knowledge_briefs,
                   source_documents_count, merged_context_payload
            from matches
            where match_id = :match_id
            """
        ),
        {"match_id": match_id},
    ).mappings().first()
    content_rows = session.execute(
        select(ContentRecord)
        .where(ContentRecord.match_id == match_id)
        .order_by(
            ContentRecord.platform.asc(),
            ContentRecord.priority.desc(),
            ContentRecord.created_at.desc(),
        )
    ).scalars().all()
    contents, content_candidates = _grouped_candidates(content_rows, match_id)
    match_info = MatchInfo(
        match_id=match.match_id,
        league=match.league,
        match_time=match.match_time,
        home_team=(extra or {}).get("home_team") or "Unknown",
        away_team=(extra or {}).get("away_team") or "Unknown",
        home_logo_url=(extra or {}).get("home_logo_url"),
        away_logo_url=(extra or {}).get("away_logo_url"),
        competition_logo_url=(extra or {}).get("competition_logo_url"),
        fixture_status=(extra or {}).get("fixture_status"),
        fixture_status_text=(extra or {}).get("fixture_status_text"),
        home_rank=(extra or {}).get("home_rank"),
        away_rank=(extra or {}).get("away_rank"),
        home_recent_form=json_loads((extra or {}).get("home_recent_form")) or [],
        away_recent_form=json_loads((extra or {}).get("away_recent_form")) or [],
        injuries=json_loads((extra or {}).get("injuries")) or [],
        odds=json_loads((extra or {}).get("odds_payload")) or {},
        rank_source=(extra or {}).get("rank_source"),
        form_source=(extra or {}).get("form_source"),
        standings_summary=(extra or {}).get("standings_summary"),
        form_summary=(extra or {}).get("form_summary"),
        home_score=(extra or {}).get("home_score"),
        away_score=(extra or {}).get("away_score"),
        home_elo=(extra or {}).get("home_elo"),
        away_elo=(extra or {}).get("away_elo"),
        home_elo_rank=(extra or {}).get("home_elo_rank"),
        away_elo_rank=(extra or {}).get("away_elo_rank"),
        knowledge_briefs=json_loads((extra or {}).get("knowledge_briefs")) or [],
        source_documents_count=(extra or {}).get("source_documents_count") or 0,
        merged_context=json_loads((extra or {}).get("merged_context_payload")) or {},
        must_fill=match.status == "ready",
    )
    return {"match": match_info, "contents": contents, "content_candidates": content_candidates}
