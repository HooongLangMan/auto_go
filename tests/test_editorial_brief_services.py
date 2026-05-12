from auto_football.domain.services.editorial_brief_service import EditorialBriefService
from auto_football.domain.services.outline_planner_service import OutlinePlannerService
from auto_football.domain.services.style_router_service import StyleRouterService
from auto_football.schemas import (
    AudienceLevel,
    ContentReadiness,
    EditorialStance,
    FactBlockConfidence,
    FactPack,
    OutlineSelection,
    Platform,
    StyleSelection,
)


def test_low_readiness_xhs_routes_to_cautious_quicktake_plan() -> None:
    pack = FactPack(
        match_id=3001,
        platform=Platform.XIAOHONGSHU,
        mode="pre_match",
        readiness=ContentReadiness.LOW,
        competition_context={"summary": ""},
        form_signals={"summary": ""},
        availability_signals={},
        market_signals={},
        historical_signals={},
        knowledge_signals={"language_goal": "Write for mainstream readers"},
        narrative_hooks=["caution due to thin inputs"],
        data_gaps=[],
        confidence=FactBlockConfidence(overall=0.35, block_scores={}),
    )

    brief = EditorialBriefService().build(pack)
    style = StyleRouterService().choose(pack, brief, recent_styles=[StyleSelection.ANALYST])
    outline = OutlinePlannerService().choose(
        pack,
        brief,
        style,
        recent_pairs=[(StyleSelection.ANALYST, OutlineSelection.VERDICT_FIRST)],
    )

    assert brief.audience_level is AudienceLevel.MAINSTREAM
    assert brief.stance is EditorialStance.CAUTIOUS
    assert style is StyleSelection.CALM_QUICKTAKE
    assert outline is OutlineSelection.CAUTIOUS_GAP_AWARE


def test_wechat_brief_diversifies_style_and_outline_after_recent_reuse() -> None:
    pack = FactPack(
        match_id=3002,
        platform=Platform.WECHAT,
        mode="pre_match",
        readiness=ContentReadiness.MEDIUM,
        competition_context={"summary": "Table position keeps the matchup relevant."},
        form_signals={"summary": "Recent form points to a competitive game."},
        availability_signals={},
        market_signals={},
        historical_signals={},
        knowledge_signals={"language_goal": "Use plain football language."},
        narrative_hooks=["This match has enough signal for a balanced read."],
        data_gaps=[],
        confidence=FactBlockConfidence(overall=0.72, block_scores={}),
    )

    brief = EditorialBriefService().build(pack)
    style = StyleRouterService().choose(pack, brief, recent_styles=[StyleSelection.ANALYST])
    outline = OutlinePlannerService().choose(
        pack,
        brief,
        style,
        recent_pairs=[(StyleSelection.MEDIA_COMMENTARY, OutlineSelection.VERDICT_FIRST)],
    )

    assert brief.audience_level is AudienceLevel.INFORMED
    assert brief.stance is EditorialStance.BALANCED
    assert style is StyleSelection.MEDIA_COMMENTARY
    assert outline is OutlineSelection.TREND_BREAKDOWN
