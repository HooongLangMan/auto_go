from __future__ import annotations

from auto_football.schemas import (
    ContentReadiness,
    FactBlockConfidence,
    FactGap,
    FactPack,
    MatchInfo,
    RoutedContentPlan,
)


class FactPackService:
    def build(self, match: MatchInfo, plan: RoutedContentPlan) -> FactPack:
        merged_context = match.merged_context or {}
        missing_players = list(match.external_missing_players) or [
            *list(merged_context.get("home_missing_players") or []),
            *list(merged_context.get("away_missing_players") or []),
        ]
        availability_summary = match.external_availability_summary or merged_context.get("whoscored_availability_summary")
        competition_context = {
            "league": match.league,
            "match_time": match.match_time,
            "home_team": match.home_team,
            "away_team": match.away_team,
            "rank_snapshot": {
                "home_rank": match.home_rank,
                "away_rank": match.away_rank,
                "source": match.rank_source,
            },
            "standings_summary": match.standings_summary,
            "sections": self._section_rules(match),
        }

        form_signals = {
            "home_recent_form": match.home_recent_form,
            "away_recent_form": match.away_recent_form,
            "summary": match.form_summary,
            "source": match.form_source,
        }
        availability_signals = {
            "injuries": match.injuries or [],
            "missing_players": missing_players,
            "external_summary": availability_summary,
            "summary": self._availability_summary(match),
        }
        market_signals = {
            "odds": match.odds or {},
            "summary": self._market_summary(match),
        }
        historical_signals: dict[str, object] = {
            "fbref_team_stat_summaries": merged_context.get("fbref_team_stat_summaries", {}),
            "summary": self._historical_summary(match),
        }
        knowledge_signals = {
            "briefs": match.knowledge_briefs,
            "language_goal": "Write for mainstream readers using plain language and grounded football context.",
            "strength_snapshot": self._strength_snapshot(match),
            "source_documents_count": match.source_documents_count,
        }
        narrative_hooks = self._build_narrative_hooks(match)

        data_gaps: list[FactGap] = []
        block_scores = {
            "competition_context": self._score_competition_context(match),
            "form_signals": self._score_form_signals(match, data_gaps),
            "availability_signals": self._score_availability_signals(match, data_gaps),
            "market_signals": self._score_market_signals(match, data_gaps),
            "historical_signals": 0.2,
            "knowledge_signals": self._score_knowledge_signals(match, data_gaps),
        }
        confidence = FactBlockConfidence(
            overall=round(sum(block_scores.values()) / len(block_scores), 2),
            block_scores=block_scores,
        )

        readiness = self._score_readiness(data_gaps, block_scores)

        return FactPack(
            match_id=match.match_id,
            platform=plan.platform,
            mode=plan.mode,
            readiness=readiness,
            competition_context=competition_context,
            form_signals=form_signals,
            availability_signals=availability_signals,
            market_signals=market_signals,
            historical_signals=historical_signals,
            knowledge_signals=knowledge_signals,
            narrative_hooks=narrative_hooks,
            data_gaps=data_gaps,
            confidence=confidence,
        )

    def _build_narrative_hooks(self, match: MatchInfo) -> list[str]:
        hooks = [f"{match.home_team} vs {match.away_team} is the core matchup to frame."]
        if match.home_rank and match.away_rank:
            hooks.append(
                f"Table positioning adds context: {match.home_team} are {match.home_rank}, {match.away_team} are {match.away_rank}."
            )
        if match.knowledge_briefs:
            hooks.append(match.knowledge_briefs[0])
        return hooks

    def _score_competition_context(self, match: MatchInfo) -> float:
        score = 0.4
        if match.league:
            score += 0.2
        if match.match_time:
            score += 0.2
        if match.home_team and match.away_team:
            score += 0.2
        return round(min(score, 1.0), 2)

    def _score_form_signals(self, match: MatchInfo, data_gaps: list[FactGap]) -> float:
        if match.home_recent_form and match.away_recent_form:
            return 0.9
        data_gaps.append(
            FactGap(
                field="form_signals",
                severity="high",
                message="Recent-form signals are missing for one or both teams.",
            )
        )
        return 0.1

    def _score_availability_signals(self, match: MatchInfo, data_gaps: list[FactGap]) -> float:
        if match.injuries is not None:
            return 0.8
        data_gaps.append(
            FactGap(
                field="availability_signals",
                severity="medium",
                message="Player availability and injury notes are missing.",
            )
        )
        return 0.3

    def _score_market_signals(self, match: MatchInfo, data_gaps: list[FactGap]) -> float:
        if match.odds:
            return 0.8
        data_gaps.append(
            FactGap(
                field="market_signals",
                severity="medium",
                message="Market odds are unavailable, so price-based context is thin.",
            )
        )
        return 0.3

    def _score_knowledge_signals(self, match: MatchInfo, data_gaps: list[FactGap]) -> float:
        if match.knowledge_briefs or match.source_documents_count:
            return 0.8
        data_gaps.append(
            FactGap(
                field="knowledge_signals",
                severity="low",
                message="No external knowledge briefs were attached to deepen context.",
            )
        )
        return 0.4

    def _score_readiness(self, data_gaps: list[FactGap], block_scores: dict[str, float]) -> ContentReadiness:
        high_severity_gaps = sum(1 for gap in data_gaps if gap.severity == "high")
        if high_severity_gaps or block_scores["form_signals"] < 0.4:
            return ContentReadiness.LOW
        if len(data_gaps) >= 3:
            return ContentReadiness.MEDIUM
        if all(score >= 0.75 for score in block_scores.values() if score > 0.2):
            return ContentReadiness.HIGH
        return ContentReadiness.MEDIUM

    def _availability_summary(self, match: MatchInfo) -> str:
        merged_context = match.merged_context or {}
        if match.external_availability_summary:
            return match.external_availability_summary
        if merged_context.get("whoscored_availability_summary"):
            return str(merged_context.get("whoscored_availability_summary"))
        if match.injuries:
            listed = "; ".join(match.injuries[:3])
            return f"Confirmed availability concerns: {listed}"
        return "No confirmed injury list is available."

    def _historical_summary(self, match: MatchInfo) -> str:
        merged_context = match.merged_context or {}
        stat_summaries = merged_context.get("fbref_team_stat_summaries") or {}
        ordered = [stat_summaries.get(match.home_team), stat_summaries.get(match.away_team)]
        summaries = [item for item in ordered if isinstance(item, str) and item.strip()]
        if summaries:
            return " ".join(summaries)
        return "No structured historical or advanced-stat summary is available."

    def _market_summary(self, match: MatchInfo) -> str:
        odds = match.odds or {}
        european = ((odds.get("eu") or {}).get("immediate") or {}) if isinstance(odds, dict) else {}
        parts: list[str] = []
        if european.get("win"):
            parts.append(f"home {european['win']}")
        if european.get("draw"):
            parts.append(f"draw {european['draw']}")
        if european.get("fail"):
            parts.append(f"away {european['fail']}")
        if parts:
            return "European market snapshot: " + " | ".join(parts)
        return "No reliable market summary is available."

    def _strength_snapshot(self, match: MatchInfo) -> str:
        if match.home_elo is not None and match.away_elo is not None:
            return (
                f"Long-term strength signal: {match.home_team} {match.home_elo:.1f} "
                f"vs {match.away_team} {match.away_elo:.1f}"
            )
        return "Long-term strength signal is limited."

    def _section_rules(self, match: MatchInfo) -> dict[str, str]:
        sections = {
            "background": "include",
            "form": "include",
            "availability": "include",
            "market": "include",
        }
        if match.home_rank is None and match.away_rank is None:
            sections["background"] = "skip"
        if not match.home_recent_form and not match.away_recent_form:
            sections["form"] = "skip"
        if not match.injuries and not match.external_missing_players and not match.external_availability_summary:
            sections["availability"] = "skip"
        if not match.odds:
            sections["market"] = "skip"
        return sections
