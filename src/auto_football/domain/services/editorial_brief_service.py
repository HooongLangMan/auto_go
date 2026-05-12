from __future__ import annotations

from auto_football.schemas import (
    AudienceLevel,
    ContentReadiness,
    EditorialBrief,
    EditorialStance,
    FactPack,
    Platform,
)


class EditorialBriefService:
    def build(self, pack: FactPack) -> EditorialBrief:
        audience_level = self._audience_level(pack)
        stance = self._stance(pack)

        return EditorialBrief(
            platform=pack.platform,
            mode=pack.mode,
            audience_level=audience_level,
            stance=stance,
            primary_angle=self._primary_angle(pack),
            secondary_angles=self._secondary_angles(pack),
            core_claim=self._core_claim(stance),
            supporting_evidence=self._supporting_evidence(pack),
            discussion_hook=self._discussion_hook(pack),
            prohibited_moves=self._prohibited_moves(stance),
            plain_language_guidance=self._plain_language_guidance(pack),
        )

    def _audience_level(self, pack: FactPack) -> AudienceLevel:
        if pack.platform is Platform.XIAOHONGSHU:
            return AudienceLevel.MAINSTREAM
        return AudienceLevel.INFORMED

    def _stance(self, pack: FactPack) -> EditorialStance:
        if pack.readiness in {ContentReadiness.LOW, ContentReadiness.REVIEW_HEAVY}:
            return EditorialStance.CAUTIOUS
        return EditorialStance.BALANCED

    def _primary_angle(self, pack: FactPack) -> str:
        if pack.narrative_hooks:
            return pack.narrative_hooks[0]
        return "Frame the match with verified context only."

    def _secondary_angles(self, pack: FactPack) -> list[str]:
        return pack.narrative_hooks[1:3]

    def _core_claim(self, stance: EditorialStance) -> str:
        if stance is EditorialStance.CAUTIOUS:
            return "The available inputs support a measured read, not a hard take."
        return "The current inputs support a clear match-angle read."

    def _supporting_evidence(self, pack: FactPack) -> list[str]:
        evidence: list[str] = []
        for block in (pack.competition_context, pack.form_signals, pack.knowledge_signals):
            summary = block.get("summary")
            if isinstance(summary, str) and summary:
                evidence.append(summary)
        return evidence

    def _discussion_hook(self, pack: FactPack) -> str:
        if pack.readiness is ContentReadiness.LOW:
            return "Which missing signal would change your read of this matchup the most?"
        return "What angle stands out most from the available signals?"

    def _prohibited_moves(self, stance: EditorialStance) -> list[str]:
        if stance is EditorialStance.CAUTIOUS:
            return ["Do not overstate certainty.", "Do not invent missing evidence."]
        return ["Do not drift away from the fact pack."]

    def _plain_language_guidance(self, pack: FactPack) -> list[str]:
        guidance = []
        language_goal = pack.knowledge_signals.get("language_goal")
        if isinstance(language_goal, str) and language_goal:
            guidance.append(language_goal)
        guidance.append("Keep claims specific and easy to follow.")
        return guidance
