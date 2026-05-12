from __future__ import annotations

from auto_football.schemas import CandidateEvaluation, GeneratedContent


class CandidateRankingService:
    def rank(
        self,
        candidates: list[tuple[GeneratedContent, CandidateEvaluation]],
    ) -> list[tuple[GeneratedContent, CandidateEvaluation]]:
        # Title is only a deterministic fallback when quality signals tie.
        return sorted(
            candidates,
            key=lambda item: (
                item[1].hard_fail,
                -item[1].overall_score,
                -item[1].plain_language_score,
                item[0].title,
            ),
        )
