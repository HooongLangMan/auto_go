from datetime import datetime, timezone

from auto_football.clients import ChatCompletionClient
from auto_football.domain.services.fact_pack_service import FactPackService
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


def test_fact_pack_marks_background_section_skip_when_ranking_is_missing() -> None:
    match = MatchInfo(
        match_id=7501,
        league="Premier League",
        match_time=datetime(2026, 5, 6, 19, 0, tzinfo=timezone.utc),
        home_team="Liverpool",
        away_team="Aston Villa",
        home_recent_form=["W", "L", "W", "W", "L"],
        away_recent_form=["D", "W", "L", "D", "W"],
        standings_summary="暂无稳定联赛排名数据。",
        form_summary="利物浦近期波动较大，维拉走势也不算稳定。",
        odds={"eu": {"immediate": {"win": "1.80", "draw": "3.20", "fail": "4.50"}}},
    )
    plan = RoutedContentPlan(
        match_id=7501,
        platform=Platform.WECHAT,
        mode=ContentMode.PRE_MATCH,
        account_id="wechat-main",
        score=100,
        priority=100,
        reason="test",
    )

    pack = FactPackService().build(match, plan)

    assert pack.competition_context["sections"]["background"] == "skip"
    assert pack.competition_context["sections"]["form"] == "include"


def test_writer_prompt_tells_model_to_omit_background_section_when_missing() -> None:
    client = ChatCompletionClient.__new__(ChatCompletionClient)
    pack = FactPack(
        match_id=7502,
        platform=Platform.WECHAT,
        mode=ContentMode.PRE_MATCH,
        readiness=ContentReadiness.MEDIUM,
        competition_context={"summary": "", "sections": {"background": "skip", "form": "include", "availability": "include", "market": "include"}},
        form_signals={"summary": "Home form is stronger."},
        availability_signals={"summary": "Two home absences matter."},
        market_signals={"summary": "Home win shortest."},
        historical_signals={},
        knowledge_signals={"language_goal": "Write for mainstream readers"},
        narrative_hooks=["home edge"],
        data_gaps=[],
        confidence=FactBlockConfidence(overall=0.75, block_scores={}),
    )
    brief = EditorialBrief(
        platform=Platform.WECHAT,
        mode=ContentMode.PRE_MATCH,
        audience_level=AudienceLevel.MAINSTREAM,
        stance=EditorialStance.BALANCED,
        primary_angle="home edge",
        secondary_angles=[],
        core_claim="Home side is more likely to take points.",
        supporting_evidence=["Home form is stronger."],
        discussion_hook="",
        prohibited_moves=[],
        plain_language_guidance=["Keep it plain."],
    )

    prompt = client._build_candidate_prompt(
        pack=pack,
        brief=brief,
        style=StyleSelection.ANALYST,
        outline=OutlineSelection.VERDICT_FIRST,
    )

    assert "Section rules:" in prompt.user_prompt
    assert '"background": "skip"' in prompt.user_prompt


def test_fallback_wechat_omits_background_paragraph_when_section_is_skip(tmp_path) -> None:
    from auto_football.config import Settings
    from auto_football.pipeline import AutoFootballPipeline

    pipeline = AutoFootballPipeline(Settings(DATABASE_URL=f"sqlite+pysqlite:///{(tmp_path / 'slots.db').as_posix()}", RUN_DRY=True))
    match = MatchInfo(
        match_id=7503,
        league="Premier League",
        match_time=datetime(2026, 5, 6, 19, 0, tzinfo=timezone.utc),
        home_team="Liverpool",
        away_team="Aston Villa",
        home_recent_form=["W", "L", "W", "W", "L"],
        away_recent_form=["D", "W", "L", "D", "W"],
        standings_summary="暂无稳定联赛排名数据。",
        form_summary="利物浦近期波动较大，维拉走势也不算稳定。",
        odds={"eu": {"immediate": {"win": "1.80", "draw": "3.20", "fail": "4.50"}}},
        merged_context={"coverage": {"ready": True}, "section_rules": {"background": "skip", "form": "include", "availability": "include", "market": "include"}},
    )

    content = pipeline._fallback_wechat(match)

    assert "当前数据未覆盖" not in content.content
    assert "暂无稳定联赛排名数据" not in content.content
