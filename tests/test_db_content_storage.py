from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from sqlalchemy import text

from auto_football.config import Settings
from auto_football.db import ContentRecord, Database
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


def test_database_keeps_multiple_drafts_for_same_match(tmp_path) -> None:
    db_path = tmp_path / "router.db"
    settings = Settings(DATABASE_URL=f"sqlite+pysqlite:///{db_path.as_posix()}")
    db = Database(settings)
    db.init_db()

    match = MatchInfo(
        match_id=9001,
        league="Premier League",
        match_time=datetime(2026, 4, 25, 20, 0, tzinfo=timezone.utc),
        home_team="Liverpool",
        away_team="Arsenal",
        fixture_status="FT",
        fixture_status_text="Finished",
        home_score=2,
        away_score=1,
        must_fill=True,
    )
    db.upsert_match(match)

    db.save_content(
        GeneratedContent(
            match_id=9001,
            platform=Platform.WECHAT,
            mode=ContentMode.RESULT_FLASH,
            account_id="wechat-main",
            status=ContentStatus.READY_TO_PUBLISH,
            priority=90,
            title="赛果快评",
            content="这是一篇赛果快评。",
            images=["cover.png"],
            remote_images=["https://example.com/action.jpg"],
            source_urls=["https://example.com/report"],
            tags=["赛果", "英超", "快评"],
        )
    )
    db.save_content(
        GeneratedContent(
            match_id=9001,
            platform=Platform.XIAOHONGSHU,
            mode=ContentMode.HOT_RECAP,
            account_id="xhs-main",
            status=ContentStatus.READY_TO_PUBLISH,
            priority=80,
            title="热点复盘",
            content="这是一篇热点复盘。",
            images=["poster.png"],
            remote_images=["https://example.com/hot.jpg"],
            source_urls=["https://example.com/hot"],
            primary_media_path="poster.png",
            tags=["热点", "复盘"],
        )
    )

    with db.session() as session:
        rows = session.query(ContentRecord).filter(ContentRecord.match_id == 9001).all()
        assert {row.publish_channel for row in rows} == {"wechat", "xiaohongshu"}
        assert any(row.primary_media_path == "cover.png" for row in rows)
        assert any(row.tags == ["热点", "复盘"] for row in rows)

    payload = db.get_preview_payloads(match_id=9001, limit_matches=1)[0]

    assert len(payload["contents"]) == 2
    assert {item["mode"] for item in payload["contents"]} == {"result_flash", "hot_recap"}
    assert {item["account_id"] for item in payload["contents"]} == {"wechat-main", "xhs-main"}
    assert {item["publish_channel"] for item in payload["contents"]} == {"wechat", "xiaohongshu"}
    assert {item["primary_media_path"] for item in payload["contents"]} == {"cover.png", "poster.png"}
    assert any(item["tags"] == ["赛果", "英超", "快评"] for item in payload["contents"])
    assert all(item["status"] == "ready_to_publish" for item in payload["contents"])


def test_database_migrates_retired_publish_status(tmp_path) -> None:
    db_path = tmp_path / "legacy_status.db"
    settings = Settings(DATABASE_URL=f"sqlite+pysqlite:///{db_path.as_posix()}")
    db = Database(settings)
    db.init_db()
    db.upsert_match(
        MatchInfo(
            match_id=9002,
            league="Premier League",
            match_time=datetime(2026, 4, 25, 20, 0, tzinfo=timezone.utc),
            home_team="Liverpool",
            away_team="Arsenal",
        )
    )
    db.save_content(
        GeneratedContent(
            match_id=9002,
            platform=Platform.XIAOHONGSHU,
            mode=ContentMode.PRE_MATCH,
            account_id="xhs-main",
            status=ContentStatus.READY_TO_PUBLISH,
            title="赛前分析",
            content="这是一篇赛前分析。",
        )
    )
    with db.session() as session:
        legacy_status = "ready_for_" + chr(114) + chr(112) + chr(97)
        session.execute(text("update contents set status = :status where match_id = 9002"), {"status": legacy_status})
        session.commit()

    db.init_db()

    with db.session() as session:
        status = session.execute(text("select status from contents where match_id = 9002")).scalar_one()
    assert status == "ready_to_publish"


def test_database_migrates_legacy_sqlite_contents_tags_column(tmp_path) -> None:
    db_path = tmp_path / "legacy_tags.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        create table contents (
            id integer primary key autoincrement,
            match_id integer not null,
            platform varchar(32),
            publish_channel varchar(32),
            mode varchar(32),
            account_id varchar(64),
            status varchar(32),
            priority integer,
            title varchar(256),
            content text,
            images json,
            remote_images json,
            source_urls json,
            primary_media_path text,
            created_at datetime
        )
        """
    )
    conn.execute(
        """
        insert into contents (
            match_id, platform, publish_channel, mode, account_id, status, priority,
            title, content, images, remote_images, source_urls, primary_media_path, created_at
        ) values (
            9003, 'wechat', 'wechat', 'pre_match', 'wechat-main', 'drafted', 1,
            '旧草稿', '旧内容', '[]', '[]', '[]', null, '2026-04-25 20:00:00'
        )
        """
    )
    conn.commit()
    conn.close()

    settings = Settings(DATABASE_URL=f"sqlite+pysqlite:///{db_path.as_posix()}")
    db = Database(settings)

    db.init_db()

    with db.session() as session:
        tags = session.query(ContentRecord).filter(ContentRecord.match_id == 9003).one().tags
    assert tags == []


def test_upsert_match_persists_logo_urls(tmp_path) -> None:
    db_path = tmp_path / "match_logos.db"
    settings = Settings(DATABASE_URL=f"sqlite+pysqlite:///{db_path.as_posix()}")
    db = Database(settings)
    db.init_db()

    db.upsert_match(
        MatchInfo(
            match_id=9004,
            league="Premier League",
            match_time=datetime(2026, 4, 25, 20, 0, tzinfo=timezone.utc),
            home_team="Nottingham Forest",
            away_team="Aston Villa",
            home_logo_url="https://example.com/home.png",
            away_logo_url="https://example.com/away.png",
            competition_logo_url="https://example.com/league.png",
        )
    )

    with db.session() as session:
        row = session.execute(
            text(
                """
                select home_logo_url, away_logo_url, competition_logo_url
                from matches
                where match_id = 9004
                """
            )
        ).one()

    assert row.home_logo_url == "https://example.com/home.png"
    assert row.away_logo_url == "https://example.com/away.png"
    assert row.competition_logo_url == "https://example.com/league.png"


def test_upsert_match_persists_enrichment_fields(tmp_path) -> None:
    db_path = tmp_path / "match_enrichment_fields.db"
    settings = Settings(DATABASE_URL=f"sqlite+pysqlite:///{db_path.as_posix()}")
    db = Database(settings)
    db.init_db()

    db.upsert_match(
        MatchInfo(
            match_id=9005,
            league="Premier League",
            match_time=datetime(2026, 4, 25, 20, 0, tzinfo=timezone.utc),
            home_team="Liverpool",
            away_team="Arsenal",
            home_rank=2,
            away_rank=4,
            home_recent_form=["W", "W", "D", "W", "L"],
            away_recent_form=["L", "D", "W", "L", "W"],
            injuries=["Bukayo Saka: Hamstring (Doubtful)"],
            odds={"eu": {"immediate": {"win": "1.80", "draw": "3.20", "fail": "4.50"}}},
            rank_source="football_data",
            form_source="sofascore",
            standings_summary="Liverpool are second and Arsenal are fourth.",
            form_summary="Liverpool carry the stronger recent trend.",
            source_documents_count=3,
            merged_context={"coverage": {"total_signals": 6, "ready": True}},
        )
    )

    bundle = db.get_match_bundle(9005)
    match = bundle["match"]

    assert match.home_rank == 2
    assert match.away_rank == 4
    assert match.home_recent_form == ["W", "W", "D", "W", "L"]
    assert match.away_recent_form == ["L", "D", "W", "L", "W"]
    assert match.injuries == ["Bukayo Saka: Hamstring (Doubtful)"]
    assert match.odds == {"eu": {"immediate": {"win": "1.80", "draw": "3.20", "fail": "4.50"}}}
    assert match.rank_source == "football_data"
    assert match.form_source == "sofascore"
    assert match.standings_summary == "Liverpool are second and Arsenal are fourth."
    assert match.form_summary == "Liverpool carry the stronger recent trend."


def test_get_match_bundle_returns_match_and_latest_content_state(tmp_path) -> None:
    db_path = tmp_path / "bundle.db"
    settings = Settings(DATABASE_URL=f"sqlite+pysqlite:///{db_path.as_posix()}")
    db = Database(settings)
    db.init_db()

    db.upsert_match(
        MatchInfo(
            match_id=9010,
            league="Premier League",
            match_time=datetime(2026, 4, 25, 20, 0, tzinfo=timezone.utc),
            home_team="Liverpool",
            away_team="Arsenal",
            home_logo_url="https://example.com/home.png",
            away_logo_url="https://example.com/away.png",
            competition_logo_url="https://example.com/league.png",
            fixture_status="NS",
            fixture_status_text="Not Started",
            knowledge_briefs=["[clubelo] Liverpool edge"],
            source_documents_count=2,
            merged_context={"summary": "merged"},
        )
    )
    db.save_content(
        GeneratedContent(
            match_id=9010,
            platform=Platform.WECHAT,
            mode=ContentMode.PRE_MATCH,
            account_id="wechat-main",
            status=ContentStatus.READY_TO_PUBLISH,
            priority=12,
            title="微信稿",
            content="正文 A",
            images=["cover-a.png"],
            tags=["赛前"],
        )
    )
    db.save_content(
        GeneratedContent(
            match_id=9010,
            platform=Platform.XIAOHONGSHU,
            mode=ContentMode.PRE_MATCH,
            account_id="xhs-main",
            status=ContentStatus.DRAFTED,
            priority=7,
            title="小红书稿",
            content="正文 B",
            images=["cover-b.png"],
            tags=["争议"],
        )
    )

    bundle = db.get_match_bundle(9010)

    assert bundle is not None
    match = bundle["match"]
    contents = bundle["contents"]
    assert match.home_logo_url == "https://example.com/home.png"
    assert match.away_logo_url == "https://example.com/away.png"
    assert match.competition_logo_url == "https://example.com/league.png"
    assert match.knowledge_briefs == ["[clubelo] Liverpool edge"]
    assert match.source_documents_count == 2
    assert match.merged_context == {"summary": "merged"}
    assert contents["wechat"].title == "微信稿"
    assert contents["wechat"].status is ContentStatus.READY_TO_PUBLISH
    assert contents["xiaohongshu"].title == "小红书稿"
    assert contents["xiaohongshu"].status is ContentStatus.DRAFTED
def test_database_preserves_ranked_alternate_candidates_for_same_platform_and_mode(tmp_path) -> None:
    db_path = tmp_path / "candidate_rank.db"
    settings = Settings(DATABASE_URL=f"sqlite+pysqlite:///{db_path.as_posix()}")
    db = Database(settings)
    db.init_db()

    db.upsert_match(
        MatchInfo(
            match_id=7001,
            league="Premier League",
            match_time=datetime(2026, 4, 25, 20, 0, tzinfo=timezone.utc),
            home_team="Liverpool",
            away_team="Arsenal",
        )
    )

    db.save_contents(
        [
            GeneratedContent(
                match_id=7001,
                platform=Platform.WECHAT,
                mode=ContentMode.PRE_MATCH,
                account_id="wechat-main",
                status=ContentStatus.READY_TO_PUBLISH,
                title="Top candidate",
                content="Top body",
                candidate_rank=1,
                candidate_count=2,
                candidate_group="group-7001",
                editorial_style=StyleSelection.ANALYST,
                editorial_outline=OutlineSelection.VERDICT_FIRST,
                content_readiness=ContentReadiness.HIGH,
            ),
            GeneratedContent(
                match_id=7001,
                platform=Platform.WECHAT,
                mode=ContentMode.PRE_MATCH,
                account_id="wechat-main",
                status=ContentStatus.DRAFTED,
                title="Backup candidate",
                content="Backup body",
                candidate_rank=2,
                candidate_count=2,
                candidate_group="group-7001",
                editorial_style=StyleSelection.MEDIA_COMMENTARY,
                editorial_outline=OutlineSelection.TREND_BREAKDOWN,
                content_readiness=ContentReadiness.HIGH,
            ),
        ]
    )

    bundle = db.get_match_bundle(7001)

    assert bundle is not None
    assert bundle["contents"]["wechat"].title == "Top candidate"
    assert bundle["contents"]["wechat"].account_id == "wechat-main"
    candidates = bundle["content_candidates"]["wechat"]
    assert [item.candidate_rank for item in candidates] == [1, 2]
    assert all(item.account_id == "wechat-main" for item in candidates)
    assert candidates[0].status is ContentStatus.READY_TO_PUBLISH
    assert candidates[1].status is ContentStatus.DRAFTED


def test_database_prunes_stale_candidates_when_ranked_family_shrinks_on_rerun(tmp_path) -> None:
    db_path = tmp_path / "candidate_prune.db"
    settings = Settings(DATABASE_URL=f"sqlite+pysqlite:///{db_path.as_posix()}")
    db = Database(settings)
    db.init_db()

    db.upsert_match(
        MatchInfo(
            match_id=7002,
            league="Premier League",
            match_time=datetime(2026, 4, 25, 20, 0, tzinfo=timezone.utc),
            home_team="Liverpool",
            away_team="Arsenal",
        )
    )

    db.save_contents(
        [
            GeneratedContent(
                match_id=7002,
                platform=Platform.WECHAT,
                mode=ContentMode.PRE_MATCH,
                account_id="wechat-main",
                status=ContentStatus.READY_TO_PUBLISH,
                title="First run top",
                content="Top body",
                candidate_rank=1,
                candidate_count=3,
                candidate_group="group-7002-v1",
            ),
            GeneratedContent(
                match_id=7002,
                platform=Platform.WECHAT,
                mode=ContentMode.PRE_MATCH,
                account_id="wechat-main",
                status=ContentStatus.DRAFTED,
                title="First run backup",
                content="Backup body",
                candidate_rank=2,
                candidate_count=3,
                candidate_group="group-7002-v1",
            ),
            GeneratedContent(
                match_id=7002,
                platform=Platform.WECHAT,
                mode=ContentMode.PRE_MATCH,
                account_id="wechat-main",
                status=ContentStatus.DRAFTED,
                title="First run third",
                content="Third body",
                candidate_rank=3,
                candidate_count=3,
                candidate_group="group-7002-v1",
            ),
        ]
    )

    db.save_contents(
        [
            GeneratedContent(
                match_id=7002,
                platform=Platform.WECHAT,
                mode=ContentMode.PRE_MATCH,
                account_id="wechat-main",
                status=ContentStatus.READY_TO_PUBLISH,
                title="Second run top",
                content="Top body v2",
                candidate_rank=1,
                candidate_count=2,
                candidate_group="group-7002-v2",
            ),
            GeneratedContent(
                match_id=7002,
                platform=Platform.WECHAT,
                mode=ContentMode.PRE_MATCH,
                account_id="wechat-main",
                status=ContentStatus.DRAFTED,
                title="Second run backup",
                content="Backup body v2",
                candidate_rank=2,
                candidate_count=2,
                candidate_group="group-7002-v2",
            ),
        ]
    )

    bundle = db.get_match_bundle(7002)

    assert bundle is not None
    candidates = bundle["content_candidates"]["wechat"]
    assert [item.candidate_rank for item in candidates] == [1, 2]
    assert [item.title for item in candidates] == ["Second run top", "Second run backup"]


def test_get_match_bundle_exposes_all_same_platform_candidate_families(tmp_path) -> None:
    db_path = tmp_path / "candidate_families.db"
    settings = Settings(DATABASE_URL=f"sqlite+pysqlite:///{db_path.as_posix()}")
    db = Database(settings)
    db.init_db()

    db.upsert_match(
        MatchInfo(
            match_id=7003,
            league="Premier League",
            match_time=datetime(2026, 4, 25, 20, 0, tzinfo=timezone.utc),
            home_team="Liverpool",
            away_team="Arsenal",
        )
    )

    db.save_contents(
        [
            GeneratedContent(
                match_id=7003,
                platform=Platform.WECHAT,
                mode=ContentMode.PRE_MATCH,
                account_id="wechat-main",
                status=ContentStatus.READY_TO_PUBLISH,
                title="Pre-match top",
                content="Pre-match top body",
                candidate_rank=1,
                candidate_count=2,
                candidate_group="group-7003-pre",
            ),
            GeneratedContent(
                match_id=7003,
                platform=Platform.WECHAT,
                mode=ContentMode.PRE_MATCH,
                account_id="wechat-main",
                status=ContentStatus.DRAFTED,
                title="Pre-match backup",
                content="Pre-match backup body",
                candidate_rank=2,
                candidate_count=2,
                candidate_group="group-7003-pre",
            ),
        ]
    )
    db.save_contents(
        [
            GeneratedContent(
                match_id=7003,
                platform=Platform.WECHAT,
                mode=ContentMode.RESULT_FLASH,
                account_id="wechat-secondary",
                status=ContentStatus.READY_TO_PUBLISH,
                title="Result top",
                content="Result top body",
                candidate_rank=1,
                candidate_count=2,
                candidate_group="group-7003-result",
            ),
            GeneratedContent(
                match_id=7003,
                platform=Platform.WECHAT,
                mode=ContentMode.RESULT_FLASH,
                account_id="wechat-secondary",
                status=ContentStatus.DRAFTED,
                title="Result backup",
                content="Result backup body",
                candidate_rank=2,
                candidate_count=2,
                candidate_group="group-7003-result",
            ),
        ]
    )

    bundle = db.get_match_bundle(7003)

    assert bundle is not None
    assert bundle["contents"]["wechat"].title == "Pre-match top"
    assert bundle["contents"]["wechat"].account_id == "wechat-main"
    candidates = bundle["content_candidates"]["wechat"]
    assert [(item.mode, item.account_id, item.candidate_rank) for item in candidates] == [
        (ContentMode.PRE_MATCH, "wechat-main", 1),
        (ContentMode.RESULT_FLASH, "wechat-secondary", 1),
        (ContentMode.PRE_MATCH, "wechat-main", 2),
        (ContentMode.RESULT_FLASH, "wechat-secondary", 2),
    ]
