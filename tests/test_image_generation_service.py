from __future__ import annotations

from datetime import datetime, timezone

from auto_football.domain.services.image_generation_service import ImageGenerationService
from auto_football.schemas import ContentMode, GeneratedContent, MatchInfo, Platform, VisualBrief, VisualBriefSlot, VisualImageType


class FakeDB:
    def __init__(self) -> None:
        self.updated = []
        self.cloned = []

    def update_content_assets(self, content) -> None:
        self.updated.append(content)

    def clone_content_assets_to_slice(self, content) -> None:
        self.cloned.append(content)


def _match() -> MatchInfo:
    return MatchInfo(
        match_id=8101,
        league="Premier League",
        match_time=datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
        home_team="Liverpool",
        away_team="Chelsea",
    )


def test_image_generation_service_uses_ai_cover_then_persists_metadata() -> None:
    db = FakeDB()
    generated: list[tuple[int, str, str]] = []

    class FakeArk:
        def generate_to_file(self, *, match_id, slug, prompt):
            generated.append((match_id, slug, prompt))
            return f"D:/fake/{match_id}_{slug}.png"

    class FakeVisualBriefs:
        def build(self, content, match):
            return [
                VisualBrief(
                    platform=content.platform,
                    slot=VisualBriefSlot.XHS_COVER,
                    image_type=VisualImageType.HYBRID_COVER,
                    scene_angle="home pressure",
                    emotion="charged",
                    subject_focus="narrative scene",
                    headline_text=content.title,
                    fallback_chain=["hybrid_cover", "fallback_card"],
                )
            ]

    class FakeFallback:
        def build_assets(self, match, verdict):
            return [f"D:/fallback/{match.match_id}_cover.png", f"D:/fallback/{match.match_id}_prediction.png"]

    service = ImageGenerationService(
        db=db,
        image_generator=FakeFallback(),
        verdict_fn=lambda match: "Liverpool不败",
        image_prompts_for_mode_fn=lambda match, mode, verdict: [f"{match.home_team} {verdict}"],
        visual_brief_service=FakeVisualBriefs(),
        ai_image_client=FakeArk(),
        settings=type(
            "Settings",
            (),
            {"ai_image_daily_limit": 6, "ai_image_per_match_limit": 1, "wechat_inline_ai_image_limit": 1},
        )(),
    )

    content = GeneratedContent(match_id=8101, platform=Platform.XIAOHONGSHU, mode=ContentMode.PRE_MATCH, title="利物浦不败", content="正文")
    result = service.generate([content], {8101: _match()})

    assert result[0].images == ["D:/fake/8101_xhs-cover.png"]
    assert result[0].editorial_metadata["visual_strategy"] == "ai_primary"
    assert result[0].editorial_metadata["image_budget_used"] == 1
    assert generated[0][0] == 8101
    assert generated[0][1] == "xhs-cover"
    assert "Liverpool vs Chelsea" in generated[0][2]
    assert "home pressure" in generated[0][2]
    assert "no text" in generated[0][2]
    assert "no typography" in generated[0][2]
    assert "no magazine layout" in generated[0][2]
    assert "no giant team logo" in generated[0][2]
    assert "no club crest dominating the frame" in generated[0][2]


def test_image_generation_service_falls_back_when_budget_is_exhausted() -> None:
    db = FakeDB()

    class FakeArk:
        def generate_to_file(self, *, match_id, slug, prompt):
            raise AssertionError("AI should not be called when budget is exhausted")

    class FakeVisualBriefs:
        def build(self, content, match):
            return [
                VisualBrief(
                    platform=content.platform,
                    slot=VisualBriefSlot.WECHAT_HERO,
                    image_type=VisualImageType.AI_ACTION_PHOTO,
                    scene_angle="home pressure",
                    emotion="tense",
                    subject_focus="action",
                    fallback_chain=["ai_action_photo", "fallback_card"],
                )
            ]

    class FakeFallback:
        def build_assets(self, match, verdict):
            return [f"D:/fallback/{match.match_id}_cover.png", f"D:/fallback/{match.match_id}_prediction.png"]

    service = ImageGenerationService(
        db=db,
        image_generator=FakeFallback(),
        verdict_fn=lambda match: "Liverpool不败",
        image_prompts_for_mode_fn=lambda match, mode, verdict: [f"{match.home_team} {verdict}"],
        visual_brief_service=FakeVisualBriefs(),
        ai_image_client=FakeArk(),
        settings=type(
            "Settings",
            (),
            {"ai_image_daily_limit": 0, "ai_image_per_match_limit": 0, "wechat_inline_ai_image_limit": 1},
        )(),
    )

    content = GeneratedContent(match_id=8101, platform=Platform.WECHAT, mode=ContentMode.PRE_MATCH, title="利物浦不败", content="正文")
    result = service.generate([content], {8101: _match()})

    assert result[0].images == ["D:/fallback/8101_cover.png", "D:/fallback/8101_prediction.png"]
    assert result[0].editorial_metadata["visual_strategy"] == "fallback_local"
    assert result[0].editorial_metadata["image_budget_used"] == 0
