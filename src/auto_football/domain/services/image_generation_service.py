from __future__ import annotations


class ImageGenerationService:
    def __init__(
        self,
        db,
        image_generator,
        verdict_fn,
        image_prompts_for_mode_fn,
        *,
        visual_brief_service=None,
        ai_image_client=None,
        settings=None,
    ) -> None:
        self.db = db
        self.image_generator = image_generator
        self.verdict_fn = verdict_fn
        self.image_prompts_for_mode_fn = image_prompts_for_mode_fn
        self.visual_brief_service = visual_brief_service
        self.ai_image_client = ai_image_client
        self.settings = settings

    def generate(self, contents, match_data):
        run_budget_used = 0
        per_match_budget: dict[int, int] = {}
        for content in contents:
            match = match_data[content.match_id]
            verdict = self.verdict_fn(match)
            briefs = self.visual_brief_service.build(content, match) if self.visual_brief_service else []
            prompts = self.image_prompts_for_mode_fn(match, content.mode, verdict)
            images = None
            budget_used = 0

            can_use_ai = bool(
                self.ai_image_client
                and self.settings is not None
                and run_budget_used < getattr(self.settings, "ai_image_daily_limit", 0)
                and per_match_budget.get(content.match_id, 0) < getattr(self.settings, "ai_image_per_match_limit", 0)
                and briefs
            )
            if can_use_ai:
                slug = "xhs-cover" if content.platform.value == "xiaohongshu" else "wechat-hero"
                ai_prompt = self._ai_prompt_from_brief(match, content, briefs[0], verdict) if briefs else (prompts[0] if prompts else "")
                image_path = self.ai_image_client.generate_to_file(
                    match_id=content.match_id,
                    slug=slug,
                    prompt=ai_prompt,
                )
                if image_path:
                    images = [image_path]
                    run_budget_used += 1
                    per_match_budget[content.match_id] = per_match_budget.get(content.match_id, 0) + 1
                    budget_used = 1

            if images is None:
                images = self.image_generator.build_assets(match, verdict)
                strategy = "fallback_local"
            else:
                strategy = "ai_primary"

            content.images = images
            content.image_prompts = prompts
            content.editorial_metadata = {
                **(content.editorial_metadata or {}),
                "visual_strategy": strategy,
                "visual_briefs": [item.model_dump(mode="json") for item in briefs],
                "image_budget_used": budget_used,
            }
            self.db.update_content_assets(content)
            self.db.clone_content_assets_to_slice(content)
        return contents

    @staticmethod
    def _ai_prompt_from_brief(match, content, brief, verdict: str) -> str:
        del verdict
        base = (
            f"professional football sports photography, {match.home_team} vs {match.away_team}, "
            f"{match.league}, {brief.scene_angle}, {brief.emotion}, {brief.subject_focus}, "
            "realistic match action, stadium lights, dynamic movement, editorial photo, news photo realism, "
            "high detail, authentic football atmosphere, clean image-only composition, no text, no title, no subtitle, "
            "no typography, no letters, no words, no caption block, no editorial page, no newspaper, no magazine layout, "
            "no poster layout, no split page, no side panel, no infographic, no watermark, no logo, no brand marks, "
            "no extra limbs, no duplicate ball, no cartoon, no 3d render"
        )
        if content.platform.value == "xiaohongshu":
            return (
                base
                + ", subject-dominant vertical football cover image, player-versus-player action as the clear focus, "
                "no giant team logo, no giant badge, no oversized crest, no club crest dominating the frame, "
                "no billboard-style club signage as the main subject, leave only subtle clean negative space, no visible text area"
            )
        return base + ", horizontal editorial hero composition, full-bleed football action frame, no visible text area"
