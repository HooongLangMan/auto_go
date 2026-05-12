from __future__ import annotations

from datetime import datetime, timezone

from auto_football.domain.services.visual_brief_service import VisualBriefService
from auto_football.schemas import ContentMode, GeneratedContent, MatchInfo, Platform, VisualBriefSlot, VisualImageType


def _match() -> MatchInfo:
    return MatchInfo(
        match_id=8001,
        league="Premier League",
        match_time=datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
        home_team="Liverpool",
        away_team="Chelsea",
        home_recent_form=["W", "W", "D", "W", "L"],
        away_recent_form=["L", "D", "W", "L", "W"],
        merged_context={"coverage": {"ready": False, "total_signals": 2}},
    )


def test_visual_brief_service_routes_wechat_pre_match_to_editorial_scene() -> None:
    service = VisualBriefService()
    content = GeneratedContent(
        match_id=8001,
        platform=Platform.WECHAT,
        mode=ContentMode.PRE_MATCH,
        title="利物浦不败，这场别想太复杂",
        content="主场压迫感会先上来。",
    )

    briefs = service.build(content, _match())

    assert briefs[0].slot is VisualBriefSlot.WECHAT_HERO
    assert briefs[0].image_type is VisualImageType.AI_ACTION_PHOTO
    assert briefs[0].scene_angle == "home pressure"
    assert briefs[0].data_dependency == "low"


def test_visual_brief_service_routes_xhs_cover_to_hybrid_claim() -> None:
    service = VisualBriefService()
    content = GeneratedContent(
        match_id=8001,
        platform=Platform.XIAOHONGSHU,
        mode=ContentMode.PRE_MATCH,
        title="利物浦不败",
        content="结论前置，主场压迫感更强。",
    )

    briefs = service.build(content, _match())

    assert briefs[0].slot is VisualBriefSlot.XHS_COVER
    assert briefs[0].image_type is VisualImageType.HYBRID_COVER
    assert briefs[0].headline_text == "利物浦不败"
