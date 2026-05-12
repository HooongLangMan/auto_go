from auto_football.domain.services.outline_planner_service import OutlinePlannerService
from auto_football.domain.services.style_router_service import StyleRouterService
from auto_football.schemas import (
    ContentReadiness,
    EditorialBrief,
    EditorialStance,
    FactBlockConfidence,
    FactPack,
    OutlineSelection,
    Platform,
    StyleSelection,
)


def _pack(summary: str, hooks: list[str], readiness: ContentReadiness = ContentReadiness.MEDIUM) -> FactPack:
    return FactPack(
        match_id=8801,
        platform=Platform.WECHAT,
        mode="pre_match",
        readiness=readiness,
        competition_context={"summary": summary},
        form_signals={"summary": "Form trend available"},
        availability_signals={"summary": "Availability notes available"},
        market_signals={"summary": "Market notes available"},
        historical_signals={},
        knowledge_signals={"language_goal": "Use clear mainstream language"},
        narrative_hooks=hooks,
        data_gaps=[],
        confidence=FactBlockConfidence(overall=0.8, block_scores={}),
    )


def _brief(pack: FactPack, stance: EditorialStance = EditorialStance.BALANCED) -> EditorialBrief:
    return EditorialBrief(
        platform=pack.platform,
        mode=pack.mode,
        audience_level="informed",
        stance=stance,
        primary_angle=pack.narrative_hooks[0],
        secondary_angles=pack.narrative_hooks[1:3],
        core_claim="The match has a clear tension line.",
        supporting_evidence=["signal"],
        discussion_hook="",
        prohibited_moves=[],
        plain_language_guidance=["Keep it plain."],
    )


def test_wechat_router_can_choose_old_hand_for_high_context_match() -> None:
    pack = _pack(
        summary="Title race pressure meets derby tension.",
        hooks=["This is the kind of match where history and pressure collide.", "form contrast"],
        readiness=ContentReadiness.HIGH,
    )
    brief = _brief(pack)

    style = StyleRouterService().choose(pack, brief, recent_styles=[StyleSelection.ANALYST, StyleSelection.MEDIA_COMMENTARY])

    assert style in {StyleSelection.OLD_HAND, StyleSelection.MEDIA_COMMENTARY, StyleSelection.ANALYST}


def test_wechat_router_prefers_media_commentary_for_medium_signal_match() -> None:
    pack = _pack(
        summary="Market edge exists but the data is not rich enough for a full old-hand treatment.",
        hooks=["The match needs a readable but not overly clinical frame.", "market tension"],
        readiness=ContentReadiness.MEDIUM,
    )
    brief = _brief(pack)

    style = StyleRouterService().choose(pack, brief, recent_styles=[])

    assert style is StyleSelection.MEDIA_COMMENTARY


def test_wechat_outline_can_move_beyond_verdict_first_when_recently_reused() -> None:
    pack = _pack(
        summary="Table pressure remains central.",
        hooks=["Momentum swing could define the night.", "market tension"],
        readiness=ContentReadiness.HIGH,
    )
    brief = _brief(pack)
    style = StyleSelection.MEDIA_COMMENTARY

    outline = OutlinePlannerService().choose(
        pack,
        brief,
        style,
        recent_pairs=[(StyleSelection.MEDIA_COMMENTARY, OutlineSelection.VERDICT_FIRST)],
    )

    assert outline in {OutlineSelection.TREND_BREAKDOWN, OutlineSelection.VERDICT_FIRST}


def test_wechat_media_commentary_prefers_trend_breakdown_outline() -> None:
    pack = _pack(
        summary="Momentum and pressure both matter here.",
        hooks=["Momentum is the real story line.", "market tension"],
        readiness=ContentReadiness.MEDIUM,
    )
    brief = _brief(pack)

    outline = OutlinePlannerService().choose(
        pack,
        brief,
        StyleSelection.MEDIA_COMMENTARY,
        recent_pairs=[],
    )

    assert outline is OutlineSelection.TREND_BREAKDOWN
