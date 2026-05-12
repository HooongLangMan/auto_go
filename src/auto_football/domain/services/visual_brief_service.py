from __future__ import annotations

from auto_football.schemas import ContentMode, GeneratedContent, MatchInfo, Platform, VisualBrief, VisualBriefSlot, VisualImageType


class VisualBriefService:
    def build(self, content: GeneratedContent, match: MatchInfo) -> list[VisualBrief]:
        scene_angle = self._scene_angle(content, match)
        if content.platform is Platform.WECHAT:
            return [
                VisualBrief(
                    platform=content.platform,
                    slot=VisualBriefSlot.WECHAT_HERO,
                    image_type=VisualImageType.AI_ACTION_PHOTO,
                    scene_angle=scene_angle,
                    emotion="tense",
                    subject_focus="match action",
                    data_dependency="low",
                    fallback_chain=["ai_action_photo", "fallback_card"],
                )
            ]
        return [
            VisualBrief(
                platform=content.platform,
                slot=VisualBriefSlot.XHS_COVER,
                image_type=VisualImageType.HYBRID_COVER,
                scene_angle=scene_angle,
                emotion="charged",
                subject_focus="narrative scene",
                headline_text=content.title,
                data_dependency="low",
                fallback_chain=["hybrid_cover", "fallback_card"],
            )
        ]

    @staticmethod
    def _scene_angle(content: GeneratedContent, match: MatchInfo) -> str:
        del match
        text = f"{content.title}\n{content.content}"
        if "不败" in text or "压迫" in text:
            return "home pressure"
        if content.mode is ContentMode.RESULT_FLASH:
            return "result emotion"
        return "match tension"
