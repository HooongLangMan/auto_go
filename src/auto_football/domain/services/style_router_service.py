from __future__ import annotations

from auto_football.schemas import (
    EditorialBrief,
    EditorialStance,
    FactPack,
    Platform,
    StyleSelection,
)


class StyleRouterService:
    def choose(
        self,
        pack: FactPack,
        brief: EditorialBrief,
        recent_styles: list[StyleSelection] | None = None,
    ) -> StyleSelection:
        recent_styles = recent_styles or []

        if brief.platform is Platform.XIAOHONGSHU and brief.stance is EditorialStance.CAUTIOUS:
            return StyleSelection.CALM_QUICKTAKE

        if brief.platform is Platform.WECHAT:
            hooks = " ".join(pack.narrative_hooks).lower()
            if pack.readiness.value == "high" and any(token in hooks for token in ("history", "pressure", "derby", "collide", "swing")):
                if not recent_styles or recent_styles[-1] is not StyleSelection.OLD_HAND:
                    return StyleSelection.OLD_HAND
            if pack.readiness.value == "medium":
                if not recent_styles or recent_styles[-1] is not StyleSelection.MEDIA_COMMENTARY:
                    return StyleSelection.MEDIA_COMMENTARY
            if recent_styles and recent_styles[-1] is StyleSelection.ANALYST:
                return StyleSelection.MEDIA_COMMENTARY
            return StyleSelection.ANALYST

        preferred = StyleSelection.ANALYST
        if recent_styles and recent_styles[-1] is preferred:
            return StyleSelection.MEDIA_COMMENTARY
        return preferred
