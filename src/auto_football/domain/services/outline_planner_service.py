from __future__ import annotations

from auto_football.schemas import (
    ContentReadiness,
    EditorialBrief,
    EditorialStance,
    FactPack,
    OutlineSelection,
    StyleSelection,
)


class OutlinePlannerService:
    def choose(
        self,
        pack: FactPack,
        brief: EditorialBrief,
        style: StyleSelection,
        recent_pairs: list[tuple[StyleSelection, OutlineSelection]] | None = None,
    ) -> OutlineSelection:
        recent_pairs = recent_pairs or []

        if brief.stance is EditorialStance.CAUTIOUS and style is StyleSelection.CALM_QUICKTAKE:
            return OutlineSelection.CAUTIOUS_GAP_AWARE

        if style is StyleSelection.MEDIA_COMMENTARY and pack.readiness is not ContentReadiness.LOW:
            preferred = OutlineSelection.TREND_BREAKDOWN
            if recent_pairs and recent_pairs[-1] == (style, preferred):
                return OutlineSelection.VERDICT_FIRST
            return preferred

        preferred = OutlineSelection.VERDICT_FIRST
        if recent_pairs and recent_pairs[-1] == (style, preferred):
            return OutlineSelection.TREND_BREAKDOWN
        return preferred
