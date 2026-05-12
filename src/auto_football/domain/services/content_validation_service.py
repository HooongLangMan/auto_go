from __future__ import annotations

from auto_football.schemas import (
    CandidateEvaluation,
    EditorialStance,
    FactPack,
    GeneratedContent,
    Platform,
)


class ContentValidationService:
    _JARGON_TERMS = ("elo", "expected-goals", "xg", "ppda")
    _META_PHRASES = (
        "对公众号读者来说",
        "赛前分析最重要的不是",
        "只要结论足够明确",
        "这不代表比赛一定会",
    )

    def evaluate(
        self,
        content: GeneratedContent,
        *,
        pack: FactPack,
        brief_stance: EditorialStance,
        recent_openings: list[str],
    ) -> CandidateEvaluation:
        text = content.content.strip()
        lowered = text.lower()

        plain_language_score = self._plain_language_score(lowered)
        summary_overlap_score = self._summary_overlap_score(lowered, pack)
        platform_fit_score = self._platform_fit_score(content.platform, lowered, pack)
        repetition_penalty = self._repetition_penalty(text, recent_openings)
        market_conflict_penalty = self._market_conflict_penalty(lowered, pack)
        meta_phrase_penalty = self._meta_phrase_penalty(text)
        hard_fail = not text
        overall_score = 0.0
        if not hard_fail:
            overall_score = max(
                0.0,
                (plain_language_score * 0.45)
                + (summary_overlap_score * 0.3)
                + (platform_fit_score * 0.25)
                - repetition_penalty,
            )
            overall_score = max(
                0.0,
                overall_score - market_conflict_penalty - meta_phrase_penalty,
            )
        review_summary = self._review_summary(
            plain_language_score=plain_language_score,
            summary_overlap_score=summary_overlap_score,
            platform_fit_score=platform_fit_score,
            repetition_penalty=repetition_penalty,
            market_conflict_penalty=market_conflict_penalty,
            meta_phrase_penalty=meta_phrase_penalty,
            brief_stance=brief_stance,
        )

        return CandidateEvaluation(
            plain_language_score=plain_language_score,
            fact_coverage_score=summary_overlap_score,
            platform_fit_score=platform_fit_score,
            repetition_penalty=repetition_penalty,
            overall_score=overall_score,
            review_summary=review_summary,
            hard_fail=hard_fail,
        )

    def _plain_language_score(self, lowered: str) -> float:
        score = 1.0
        for term in self._JARGON_TERMS:
            if term in lowered:
                score -= 0.3
        return max(0.0, score)

    def _summary_overlap_score(self, lowered: str, pack: FactPack) -> float:
        summaries = (
            pack.competition_context.get("summary"),
            pack.form_signals.get("summary"),
        )
        score = 0.3
        for summary in summaries:
            if isinstance(summary, str) and summary:
                for word in summary.lower().split():
                    token = word.strip(".,!?")
                    if len(token) > 3 and token in lowered:
                        score += 0.25
                        break
        return min(score, 1.0)

    def _platform_fit_score(self, platform: Platform, lowered: str, pack: FactPack) -> float:
        if platform is Platform.XIAOHONGSHU:
            score = 0.85 if len(lowered.split()) <= 20 else 0.75
            if "language_goal" in pack.knowledge_signals and self._contains_jargon(lowered):
                score -= 0.2
            return max(0.0, min(score, 1.0))
        return 0.8

    def _repetition_penalty(self, text: str, recent_openings: list[str]) -> float:
        opening = self.opening_line(text).lower()
        recent = {item.strip().lower() for item in recent_openings if item.strip()}
        if opening and opening in recent:
            return 0.2
        return 0.0

    @staticmethod
    def opening_line(text: str) -> str:
        if not text:
            return ""
        paragraphs = [item.strip() for item in text.replace("\r\n", "\n").split("\n\n") if item.strip()]
        opening = paragraphs[0] if paragraphs else text.strip()
        for marker in (". ", "。", "！", "？", "!", "?"):
            if marker in opening:
                return opening.split(marker, 1)[0].strip()
        return opening

    def _review_summary(
        self,
        *,
        plain_language_score: float,
        summary_overlap_score: float,
        platform_fit_score: float,
        repetition_penalty: float,
        market_conflict_penalty: float,
        meta_phrase_penalty: float,
        brief_stance: EditorialStance,
    ) -> str:
        return (
            f"stance={brief_stance}; plain={plain_language_score:.2f}; "
            f"coverage={summary_overlap_score:.2f}; fit={platform_fit_score:.2f}; "
            f"repetition_penalty={repetition_penalty:.2f}; "
            f"market_conflict={market_conflict_penalty:.2f}; "
            f"meta_phrase={meta_phrase_penalty:.2f}"
        )

    def _contains_jargon(self, lowered: str) -> bool:
        return any(term in lowered for term in self._JARGON_TERMS)

    def _market_conflict_penalty(self, lowered: str, pack: FactPack) -> float:
        odds = (pack.market_signals or {}).get("odds") or {}
        european = ((odds.get("eu") or {}).get("immediate") or {}) if isinstance(odds, dict) else {}
        try:
            home = float(european.get("win")) if european.get("win") is not None else None
            away = float(european.get("fail")) if european.get("fail") is not None else None
        except (TypeError, ValueError):
            return 0.0
        if home is None or away is None:
            return 0.0
        if home < away and ("客队不败" in lowered or "看好客队" in lowered or "客胜" in lowered):
            return 0.18
        if away < home and ("主队不败" in lowered or "看好主队" in lowered or "主胜" in lowered):
            return 0.18
        return 0.0

    def _meta_phrase_penalty(self, text: str) -> float:
        penalty = 0.0
        for phrase in self._META_PHRASES:
            if phrase in text:
                penalty += 0.08
        return min(penalty, 0.24)
