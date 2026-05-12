from __future__ import annotations

from datetime import date
from typing import Any

from auto_football.clients import ClubEloClient, FootballDataClient, OpenFootballClient, SofascoreClient
from auto_football.schemas import MatchInfo


class StructuredDataService:
    def __init__(
        self,
        football_data: FootballDataClient,
        sofascore: SofascoreClient,
        openfootball: OpenFootballClient,
        clubelo: ClubEloClient,
    ) -> None:
        self.football_data = football_data
        self.sofascore = sofascore
        self.openfootball = openfootball
        self.clubelo = clubelo

    def enrich_match(
        self,
        match: MatchInfo,
        *,
        run_date: date,
        api_home_stats: dict[str, Any] | None = None,
        api_away_stats: dict[str, Any] | None = None,
    ) -> MatchInfo:
        enriched = match.model_copy(deep=True)

        rank_sources: set[str] = set()
        form_sources: set[str] = set()

        if api_home_stats:
            if api_home_stats.get("rank") is not None:
                enriched.home_rank = self._safe_int(api_home_stats.get("rank"))
                rank_sources.add("api_football")
            if api_home_stats.get("form"):
                enriched.home_recent_form = self._coerce_form(api_home_stats.get("form"))
                if enriched.home_recent_form:
                    form_sources.add("api_football")

        if api_away_stats:
            if api_away_stats.get("rank") is not None:
                enriched.away_rank = self._safe_int(api_away_stats.get("rank"))
                rank_sources.add("api_football")
            if api_away_stats.get("form"):
                enriched.away_recent_form = self._coerce_form(api_away_stats.get("form"))
                if enriched.away_recent_form:
                    form_sources.add("api_football")

        home_snapshot = self.football_data.get_team_snapshot(enriched.league, enriched.home_team, limit=5)
        away_snapshot = self.football_data.get_team_snapshot(enriched.league, enriched.away_team, limit=5)
        season = self._sofascore_season(run_date)
        home_sofascore_snapshot = self.sofascore.get_team_snapshot(enriched.league, enriched.home_team, season=season, limit=5)
        away_sofascore_snapshot = self.sofascore.get_team_snapshot(enriched.league, enriched.away_team, season=season, limit=5)

        if enriched.home_rank is None and home_snapshot and home_snapshot.get("rank") is not None:
            enriched.home_rank = self._safe_int(home_snapshot.get("rank"))
            rank_sources.add("football_data")
        if enriched.away_rank is None and away_snapshot and away_snapshot.get("rank") is not None:
            enriched.away_rank = self._safe_int(away_snapshot.get("rank"))
            rank_sources.add("football_data")
        if enriched.home_rank is None and home_sofascore_snapshot and home_sofascore_snapshot.get("rank") is not None:
            enriched.home_rank = self._safe_int(home_sofascore_snapshot.get("rank"))
            rank_sources.add("sofascore")
        if enriched.away_rank is None and away_sofascore_snapshot and away_sofascore_snapshot.get("rank") is not None:
            enriched.away_rank = self._safe_int(away_sofascore_snapshot.get("rank"))
            rank_sources.add("sofascore")

        if not enriched.home_recent_form and home_snapshot:
            home_form = self._coerce_form(home_snapshot.get("recent_form"))
            if home_form:
                enriched.home_recent_form = home_form
                form_sources.add("football_data")
        if not enriched.away_recent_form and away_snapshot:
            away_form = self._coerce_form(away_snapshot.get("recent_form"))
            if away_form:
                enriched.away_recent_form = away_form
                form_sources.add("football_data")
        if not enriched.home_recent_form and home_sofascore_snapshot:
            home_form = self._coerce_form(home_sofascore_snapshot.get("recent_form"))
            if home_form:
                enriched.home_recent_form = home_form
                form_sources.add("sofascore")
        if not enriched.away_recent_form and away_sofascore_snapshot:
            away_form = self._coerce_form(away_sofascore_snapshot.get("recent_form"))
            if away_form:
                enriched.away_recent_form = away_form
                form_sources.add("sofascore")

        if not enriched.home_recent_form:
            fallback_form = self.openfootball.derive_form(enriched.league, enriched.home_team, run_date, limit=5)
            if fallback_form:
                enriched.home_recent_form = self._coerce_form(fallback_form)
                form_sources.add("openfootball")
        if not enriched.away_recent_form:
            fallback_form = self.openfootball.derive_form(enriched.league, enriched.away_team, run_date, limit=5)
            if fallback_form:
                enriched.away_recent_form = self._coerce_form(fallback_form)
                form_sources.add("openfootball")

        home_elo = self.clubelo.get_team_snapshot(run_date, enriched.home_team)
        away_elo = self.clubelo.get_team_snapshot(run_date, enriched.away_team)
        if home_elo:
            enriched.home_elo = self._safe_float(home_elo.get("Elo"))
            enriched.home_elo_rank = self._safe_int(home_elo.get("Rank"))
        if away_elo:
            enriched.away_elo = self._safe_float(away_elo.get("Elo"))
            enriched.away_elo_rank = self._safe_int(away_elo.get("Rank"))

        enriched.rank_source = self._collapse_sources(rank_sources)
        enriched.form_source = self._collapse_sources(form_sources)
        enriched.standings_summary = self._build_standings_summary(enriched)
        enriched.form_summary = self._build_form_summary(enriched)
        return enriched

    @staticmethod
    def _collapse_sources(sources: set[str]) -> str | None:
        if not sources:
            return None
        if len(sources) == 1:
            return next(iter(sources))
        return "mixed"

    @staticmethod
    def _coerce_form(value: Any) -> list[str]:
        if not value:
            return []
        if isinstance(value, str):
            parts = [item.strip().upper() for item in value.replace(",", "-").split("-") if item.strip()]
            return [item for item in parts if item in {"W", "D", "L"}]
        if isinstance(value, list):
            return [str(item).strip().upper() for item in value if str(item).strip().upper() in {"W", "D", "L"}]
        return []

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        try:
            return int(float(value)) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        try:
            return float(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _sofascore_season(run_date: date) -> int:
        return run_date.year if run_date.month >= 7 else run_date.year - 1

    @staticmethod
    def _build_standings_summary(match: MatchInfo) -> str:
        if match.home_rank is not None and match.away_rank is not None:
            return f"联赛排名方面，{match.home_team}暂列第{match.home_rank}，{match.away_team}暂列第{match.away_rank}。"
        background_parts: list[str] = []
        if match.home_elo_rank is not None:
            background_parts.append(f"{match.home_team} ClubElo第{match.home_elo_rank}")
        if match.away_elo_rank is not None:
            background_parts.append(f"{match.away_team} ClubElo第{match.away_elo_rank}")
        if background_parts:
            return "暂无稳定联赛排名数据，可参考背景强弱：" + "，".join(background_parts) + "。"
        return "暂无稳定联赛排名数据。"

    @staticmethod
    def _build_form_summary(match: MatchInfo) -> str:
        if match.home_recent_form or match.away_recent_form:
            home = "/".join(match.home_recent_form) if match.home_recent_form else "暂无"
            away = "/".join(match.away_recent_form) if match.away_recent_form else "暂无"
            return f"近期走势方面，{match.home_team}近况 {home}，{match.away_team}近况 {away}。"
        return "近期走势信息有限。"
