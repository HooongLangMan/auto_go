from __future__ import annotations

from auto_football.schemas import ContentStatus, GeneratedContent


class ContentGenerationService:
    def __init__(self, db, build_candidate_pool) -> None:
        self.db = db
        self.build_candidate_pool = build_candidate_pool

    def generate(self, content_plans, match_data) -> list[GeneratedContent]:
        contents: list[GeneratedContent] = []
        all_ranked_candidates: list[GeneratedContent] = []
        for plan in content_plans:
            match = match_data.get(plan.match_id)
            if match is None:
                continue
            candidates = list(self.build_candidate_pool(plan, match))
            if not candidates:
                self.db.clear_content_slice(
                    match_id=plan.match_id,
                    platform=plan.platform,
                    mode=plan.mode,
                    account_id=plan.account_id,
                )
                continue
            candidate_count = len(candidates)
            candidate_group = f"{plan.match_id}:{plan.platform.value}:{plan.mode.value}:{plan.account_id}"
            ranked_candidates: list[GeneratedContent] = []
            for index, candidate in enumerate(candidates, start=1):
                candidate.match_id = match.match_id
                candidate.platform = plan.platform
                candidate.mode = plan.mode
                candidate.account_id = plan.account_id
                candidate.priority = plan.priority
                candidate.candidate_rank = index
                candidate.candidate_count = candidate_count
                candidate.candidate_group = candidate_group
                candidate.status = ContentStatus.READY_TO_PUBLISH if index == 1 else ContentStatus.DRAFTED
                ranked_candidates.append(candidate)
            all_ranked_candidates.extend(ranked_candidates)
            contents.append(ranked_candidates[0])
        if all_ranked_candidates:
            self.db.save_contents(all_ranked_candidates)
        return contents
