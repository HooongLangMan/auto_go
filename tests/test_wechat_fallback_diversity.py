from datetime import datetime, timezone
from pathlib import Path

from auto_football.config import Settings
from auto_football.pipeline import AutoFootballPipeline
from auto_football.schemas import (
    AudienceLevel,
    ContentMode,
    ContentReadiness,
    EditorialBrief,
    EditorialStance,
    FactBlockConfidence,
    FactPack,
    MatchInfo,
    OutlineSelection,
    Platform,
    RoutedContentPlan,
    StyleSelection,
)


def _match() -> MatchInfo:
    return MatchInfo(
        match_id=99001,
        league="Premier League",
        match_time=datetime(2026, 5, 9, 11, 30, tzinfo=timezone.utc),
        home_team="Liverpool",
        away_team="Chelsea",
        home_recent_form=["L", "W", "W", "W", "L"],
        away_recent_form=["L", "L", "L", "L", "L"],
        odds={"eu": {"immediate": {"win": "1.80", "draw": "3.20", "fail": "4.50"}}},
        knowledge_briefs=["[clubelo] Liverpool Elo 1925 ranked 6"],
        merged_context={"section_rules": {"background": "skip", "form": "include", "availability": "skip", "market": "include"}},
    )


def _pack() -> FactPack:
    return FactPack(
        match_id=99001,
        platform=Platform.WECHAT,
        mode=ContentMode.PRE_MATCH,
        readiness=ContentReadiness.MEDIUM,
        competition_context={"sections": {"background": "skip", "form": "include", "availability": "skip", "market": "include"}},
        form_signals={"summary": "Home form stronger"},
        availability_signals={"summary": ""},
        market_signals={"summary": "Home win shortest"},
        historical_signals={},
        knowledge_signals={"language_goal": "Write for mainstream readers"},
        narrative_hooks=["Liverpool need to handle pressure without overcomplicating the game."],
        data_gaps=[],
        confidence=FactBlockConfidence(overall=0.7, block_scores={}),
    )


def _brief() -> EditorialBrief:
    return EditorialBrief(
        platform=Platform.WECHAT,
        mode=ContentMode.PRE_MATCH,
        audience_level=AudienceLevel.INFORMED,
        stance=EditorialStance.BALANCED,
        primary_angle="Liverpool need to handle pressure without overcomplicating the game.",
        secondary_angles=["Chelsea recent slide matters."],
        core_claim="Liverpool are more likely to take points.",
        supporting_evidence=["Home form stronger"],
        discussion_hook="",
        prohibited_moves=[],
        plain_language_guidance=["Keep it plain."],
    )


def test_wechat_fallback_varies_by_style_when_llm_payload_missing(tmp_path) -> None:
    pipeline = AutoFootballPipeline(
        Settings(DATABASE_URL=f"sqlite+pysqlite:///{(tmp_path / 'fallback_diversity.db').as_posix()}", RUN_DRY=True)
    )
    plan = RoutedContentPlan(
        match_id=99001,
        platform=Platform.WECHAT,
        mode=ContentMode.PRE_MATCH,
        account_id="wechat-main",
        score=100,
        priority=100,
        reason="test",
    )
    match = _match()
    pack = _pack()
    brief = _brief()

    analyst = pipeline._candidate_from_payload(
        plan, match, pack, brief, StyleSelection.ANALYST, OutlineSelection.VERDICT_FIRST, None
    )
    commentary = pipeline._candidate_from_payload(
        plan, match, pack, brief, StyleSelection.MEDIA_COMMENTARY, OutlineSelection.TREND_BREAKDOWN, None
    )
    old_hand = pipeline._candidate_from_payload(
        plan, match, pack, brief, StyleSelection.OLD_HAND, OutlineSelection.VERDICT_FIRST, None
    )

    assert analyst.content != commentary.content
    assert commentary.content != old_hand.content
    assert "对公众号读者来说" not in analyst.content
    assert "对公众号读者来说" not in commentary.content
    assert "对公众号读者来说" not in old_hand.content


def test_wechat_fallback_uses_angle_specific_openings(tmp_path) -> None:
    pipeline = AutoFootballPipeline(
        Settings(DATABASE_URL=f"sqlite+pysqlite:///{(tmp_path / 'fallback_angles.db').as_posix()}", RUN_DRY=True)
    )
    plan = RoutedContentPlan(
        match_id=99001,
        platform=Platform.WECHAT,
        mode=ContentMode.PRE_MATCH,
        account_id="wechat-main",
        score=100,
        priority=100,
        reason="test",
    )
    match = _match()
    pack = _pack()
    brief = _brief()

    market_angle = {
        "angle_id": "market_tension",
        "angle_label": "market_tension",
        "opening_instruction": "Lead with how the market and matchup tension frame the game.",
        "body_instruction": "Center the case on price pressure and where the market may still be too cautious.",
        "title_instruction": "Use a title that signals market tension without sounding like a tip sheet.",
    }
    pressure_angle = {
        "angle_id": "pressure_line",
        "angle_label": "pressure_line",
        "opening_instruction": "Lead with the pressure line and which team is more likely to carry it well.",
        "body_instruction": "Center the case on match pressure and the emotional texture of the game.",
        "title_instruction": "Use a title that signals pressure and rhythm rather than generic trend wording.",
    }

    market_candidate = pipeline._candidate_from_payload(
        plan,
        match,
        pack,
        brief,
        StyleSelection.ANALYST,
        OutlineSelection.VERDICT_FIRST,
        None,
        angle_spec=market_angle,
    )
    pressure_candidate = pipeline._candidate_from_payload(
        plan,
        match,
        pack,
        brief,
        StyleSelection.MEDIA_COMMENTARY,
        OutlineSelection.TREND_BREAKDOWN,
        None,
        angle_spec=pressure_angle,
    )

    market_opening = market_candidate.content.split("\n\n", 1)[0]
    pressure_opening = pressure_candidate.content.split("\n\n", 1)[0]

    assert market_opening != pressure_opening
    assert "先给判断" not in market_opening
    assert "先给判断" not in pressure_opening
    assert market_candidate.editorial_metadata.get("wechat_angle_id") == "market_tension"
    assert pressure_candidate.editorial_metadata.get("wechat_angle_id") == "pressure_line"


def test_wechat_hot_recap_skips_placeholder_form_comparison(tmp_path) -> None:
    pipeline = AutoFootballPipeline(
        Settings(DATABASE_URL=f"sqlite+pysqlite:///{(tmp_path / 'hot_recap_cleanup.db').as_posix()}", RUN_DRY=True)
    )
    match = MatchInfo(
        match_id=99002,
        league="UEFA Champions League",
        match_time=datetime(2026, 5, 10, 20, 0, tzinfo=timezone.utc),
        home_team="Bayern München",
        away_team="Paris Saint Germain",
        home_score=2,
        away_score=1,
        fixture_status="FT",
        fixture_status_text="Finished",
        home_recent_form=[],
        away_recent_form=[],
        knowledge_briefs=["[clubelo] Bayern München Elo 2008.3 ranked 2", "[clubelo] Paris Saint Germain Elo 1413.9 ranked None"],
    )

    content = pipeline._fallback_wechat_hot_recap(match)

    assert "待补充 vs 待补充" not in content.content


def test_wechat_cleanup_drops_raw_source_fragments_and_rank_none(tmp_path) -> None:
    pipeline = AutoFootballPipeline(
        Settings(DATABASE_URL=f"sqlite+pysqlite:///{(tmp_path / 'raw_fragment_cleanup.db').as_posix()}", RUN_DRY=True)
    )
    plan = RoutedContentPlan(
        match_id=99003,
        platform=Platform.WECHAT,
        mode=ContentMode.RESULT_FLASH,
        account_id="wechat-main",
        score=100,
        priority=100,
        reason="test",
    )
    match = MatchInfo(
        match_id=99003,
        league="Bundesliga",
        match_time=datetime(2026, 5, 10, 20, 0, tzinfo=timezone.utc),
        home_team="Bayern München",
        away_team="Paris Saint Germain",
        home_score=2,
        away_score=1,
        fixture_status="FT",
        fixture_status_text="Finished",
        home_recent_form=[],
        away_recent_form=[],
        merged_context={"section_rules": {"background": "skip", "form": "skip", "availability": "skip", "market": "skip"}},
    )
    raw_text = (
        "如果把比赛放在更长一点的窗口里看，双方近期走势大致是 待补充 vs 待补充。\n\n"
        "从现有补充信息看，[clubelo] Bayern München Elo 2008.3 ranked 2;[clubelo] Paris Saint Germain Elo 1413.9 ranked None"
    )

    cleaned = pipeline._apply_section_rules_to_generated_content(plan, match, raw_text)

    assert "待补充" not in cleaned
    assert "[clubelo]" not in cleaned
    assert "ranked None" not in cleaned


def test_wechat_angle_fallback_reaches_longform_target(tmp_path) -> None:
    pipeline = AutoFootballPipeline(
        Settings(DATABASE_URL=f"sqlite+pysqlite:///{(tmp_path / 'longform_target.db').as_posix()}", RUN_DRY=True)
    )
    plan = RoutedContentPlan(
        match_id=99004,
        platform=Platform.WECHAT,
        mode=ContentMode.PRE_MATCH,
        account_id="wechat-main",
        score=100,
        priority=100,
        reason="test",
    )
    match = _match()
    pack = _pack()
    brief = _brief()
    angle = {
        "angle_id": "strength_snapshot",
        "angle_label": "strength_snapshot",
        "opening_instruction": "Lead with long-term strength and structural edge.",
        "body_instruction": "Explain the structural edge in reader-safe longform prose.",
        "title_instruction": "Use a title about hidden edge and match control.",
    }

    candidate = pipeline._candidate_from_payload(
        plan,
        match,
        pack,
        brief,
        StyleSelection.OLD_HAND,
        OutlineSelection.TREND_BREAKDOWN,
        None,
        angle_spec=angle,
    )

    assert 800 <= len(candidate.content) <= 1200
    assert "[clubelo]" not in candidate.content


def test_wechat_longform_includes_ranking_context_when_available(tmp_path) -> None:
    pipeline = AutoFootballPipeline(
        Settings(DATABASE_URL=f"sqlite+pysqlite:///{(tmp_path / 'ranking_context.db').as_posix()}", RUN_DRY=True)
    )
    plan = RoutedContentPlan(
        match_id=99005,
        platform=Platform.WECHAT,
        mode=ContentMode.PRE_MATCH,
        account_id="wechat-main",
        score=100,
        priority=100,
        reason="test",
    )
    match = _match()
    match.home_rank = 2
    match.away_rank = 9
    match.standings_summary = "Liverpool目前第2，Chelsea目前第9，这场对双方都带着不同层级的拿分压力。"
    pack = _pack()
    brief = _brief()
    angle = {
        "angle_id": "market_tension",
        "angle_label": "market_tension",
        "opening_instruction": "Lead with market pressure.",
        "body_instruction": "Explain market pressure in longform prose.",
        "title_instruction": "Use a title about the market line.",
    }

    candidate = pipeline._candidate_from_payload(
        plan,
        match,
        pack,
        brief,
        StyleSelection.MEDIA_COMMENTARY,
        OutlineSelection.TREND_BREAKDOWN,
        None,
        angle_spec=angle,
    )

    assert "第2" in candidate.content or "Liverpool目前第2" in candidate.content
    assert "拿分压力" in candidate.content


def test_wechat_longform_skips_ranking_placeholder_when_missing(tmp_path) -> None:
    pipeline = AutoFootballPipeline(
        Settings(DATABASE_URL=f"sqlite+pysqlite:///{(tmp_path / 'ranking_placeholder.db').as_posix()}", RUN_DRY=True)
    )
    plan = RoutedContentPlan(
        match_id=99006,
        platform=Platform.WECHAT,
        mode=ContentMode.PRE_MATCH,
        account_id="wechat-main",
        score=100,
        priority=100,
        reason="test",
    )
    match = _match()
    pack = _pack()
    brief = _brief()
    angle = {
        "angle_id": "form_window",
        "angle_label": "form_window",
        "opening_instruction": "Lead with recent form.",
        "body_instruction": "Explain recent form in longform prose.",
        "title_instruction": "Use a title about form.",
    }

    candidate = pipeline._candidate_from_payload(
        plan,
        match,
        pack,
        brief,
        StyleSelection.ANALYST,
        OutlineSelection.VERDICT_FIRST,
        None,
        angle_spec=angle,
    )

    assert "暂无稳定联赛排名数据" not in candidate.content


def test_pipeline_keeps_single_wechat_helper_definition() -> None:
    source = Path("src/auto_football/pipeline.py").read_text(encoding="utf-8", errors="replace")

    assert source.count("def _fallback_wechat_variant") == 1
    assert source.count("def _fallback_wechat_result") == 1
    assert source.count("def _fallback_wechat_hot_recap") == 1
    assert source.count("def _apply_section_rules_to_generated_content") == 1
