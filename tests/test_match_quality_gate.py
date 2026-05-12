from datetime import datetime, timezone

from auto_football.config import Settings
from auto_football.pipeline import AutoFootballPipeline
from auto_football.schemas import ContentMode, MatchInfo, Platform, RoutedContentPlan


def test_low_information_match_is_blocked_from_candidate_generation(tmp_path) -> None:
    settings = Settings(DATABASE_URL=f"sqlite+pysqlite:///{(tmp_path / 'quality_gate.db').as_posix()}", RUN_DRY=True)
    pipeline = AutoFootballPipeline(settings)
    match = MatchInfo(
        match_id=7101,
        league="Premier League",
        match_time=datetime(2026, 5, 6, 19, 0, tzinfo=timezone.utc),
        home_team="Haras El Hodood",
        away_team="Masr",
        home_recent_form=[],
        away_recent_form=[],
        injuries=None,
        odds=None,
        source_documents_count=0,
        merged_context={"coverage": {"total_signals": 0, "ready": False}},
    )
    plan = RoutedContentPlan(
        match_id=7101,
        platform=Platform.WECHAT,
        mode=ContentMode.PRE_MATCH,
        account_id="wechat-main",
        score=80,
        priority=80,
        reason="test",
    )

    candidates = pipeline._build_candidate_pool(plan, match)

    assert candidates == []


def test_rich_information_match_still_generates_candidates(tmp_path) -> None:
    settings = Settings(DATABASE_URL=f"sqlite+pysqlite:///{(tmp_path / 'quality_gate_rich.db').as_posix()}", RUN_DRY=True)
    pipeline = AutoFootballPipeline(settings)
    match = MatchInfo(
        match_id=7102,
        league="Premier League",
        match_time=datetime(2026, 5, 6, 19, 0, tzinfo=timezone.utc),
        home_team="Liverpool",
        away_team="Arsenal",
        home_rank=2,
        away_rank=4,
        home_recent_form=["W", "W", "D", "W", "L"],
        away_recent_form=["L", "D", "W", "L", "W"],
        injuries=["Bukayo Saka: Hamstring (Doubtful)"],
        odds={"eu": {"immediate": {"win": "1.80", "draw": "3.20", "fail": "4.50"}}},
        knowledge_briefs=["[fbref] Liverpool recent xG edge is strong."],
        source_documents_count=4,
        merged_context={"coverage": {"total_signals": 5, "ready": True}},
    )
    plan = RoutedContentPlan(
        match_id=7102,
        platform=Platform.XIAOHONGSHU,
        mode=ContentMode.PRE_MATCH,
        account_id="xhs-main",
        score=120,
        priority=120,
        reason="test",
    )

    candidates = pipeline._build_candidate_pool(plan, match)

    assert len(candidates) >= 1
