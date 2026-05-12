from datetime import datetime, timezone

from auto_football.domain.services.fact_pack_service import FactPackService
from auto_football.schemas import ContentMode, MatchInfo, Platform, RoutedContentPlan


def test_fact_pack_marks_low_readiness_when_key_blocks_are_missing() -> None:
    match = MatchInfo(
        match_id=2001,
        league="Premier League",
        match_time=datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc),
        home_team="Liverpool",
        away_team="Arsenal",
        home_recent_form=[],
        away_recent_form=[],
        injuries=None,
        odds=None,
        knowledge_briefs=[],
    )
    plan = RoutedContentPlan(
        match_id=2001,
        platform=Platform.WECHAT,
        mode=ContentMode.PRE_MATCH,
        account_id="wechat-main",
        score=99,
        priority=99,
        reason="test",
    )

    pack = FactPackService().build(match, plan)

    assert pack.readiness.value == "low"
    assert any(gap.field == "form_signals" for gap in pack.data_gaps)
    assert "mainstream" in pack.knowledge_signals["language_goal"]


def test_fact_pack_builds_richer_signals_for_whitelist_match() -> None:
    match = MatchInfo(
        match_id=2002,
        league="UEFA Champions League",
        match_time=datetime(2026, 5, 6, 19, 0, tzinfo=timezone.utc),
        home_team="Bayern München",
        away_team="Paris Saint Germain",
        home_rank=2,
        away_rank=5,
        home_recent_form=["W", "W", "D", "W", "L"],
        away_recent_form=["L", "D", "W", "L", "W"],
        odds={"eu": {"immediate": {"win": "1.80", "draw": "3.40", "fail": "4.20"}}},
        home_elo=2008.4,
        away_elo=1413.9,
        standings_summary="Home side is chasing a major European result.",
        form_summary="Home form is stronger over the last five matches.",
        knowledge_briefs=["[clubelo] Home side has the stronger long-term profile."],
    )
    plan = RoutedContentPlan(
        match_id=2002,
        platform=Platform.WECHAT,
        mode=ContentMode.PRE_MATCH,
        account_id="wechat-main",
        score=120,
        priority=120,
        reason="test",
    )

    pack = FactPackService().build(match, plan)

    assert pack.readiness.value in {"high", "medium"}
    assert "Home side is chasing a major European result." in pack.competition_context["standings_summary"]
    assert "1.80" in pack.market_signals["summary"]
    assert "2008.4" in pack.knowledge_signals["strength_snapshot"]


def test_fact_pack_uses_external_context_summaries() -> None:
    match = MatchInfo(
        match_id=2003,
        league="Premier League",
        match_time=datetime(2026, 5, 6, 19, 0, tzinfo=timezone.utc),
        home_team="Liverpool",
        away_team="Arsenal",
        home_rank=2,
        away_rank=4,
        home_recent_form=["W", "W", "D", "W", "L"],
        away_recent_form=["L", "D", "W", "L", "W"],
        injuries=["Virgil van Dijk: Knock"],
        odds={"eu": {"immediate": {"win": "1.80", "draw": "3.40", "fail": "4.20"}}},
        standings_summary="Liverpool are chasing the title while Arsenal are protecting a top-four place.",
        form_summary="Liverpool carry the stronger recent trend.",
        knowledge_briefs=["[fbref] Liverpool recent xG edge is strong."],
        source_documents_count=4,
        merged_context={
            "fbref_team_stat_summaries": {
                "Liverpool": "Liverpool recent xG edge is strong.",
                "Arsenal": "Arsenal chance quality has dipped slightly.",
            },
            "home_missing_players": ["Alisson: Knee injury (Confirmed)"],
            "away_missing_players": ["Bukayo Saka: Hamstring (Doubtful)"],
            "whoscored_availability_summary": "Liverpool and Arsenal both have notable absences ahead of kickoff.",
        },
    )
    plan = RoutedContentPlan(
        match_id=2003,
        platform=Platform.WECHAT,
        mode=ContentMode.PRE_MATCH,
        account_id="wechat-main",
        score=110,
        priority=110,
        reason="test",
    )

    pack = FactPackService().build(match, plan)

    assert "Alisson: Knee injury (Confirmed)" in pack.availability_signals["missing_players"]
    assert "notable absences" in pack.availability_signals["external_summary"]
    assert "xG edge" in pack.historical_signals["summary"]
    assert pack.knowledge_signals["source_documents_count"] == 4
