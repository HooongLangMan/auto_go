from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from auto_football.config import Settings
from auto_football.schemas import ContentMode, RoutedContentPlan, SelectionDecision


LEAGUE_PRIORITY = {
    "UEFA Champions League": 100,
    "Premier League": 95,
    "La Liga": 90,
    "Serie A": 88,
    "Bundesliga": 87,
    "Ligue 1": 85,
    "UEFA Europa League": 82,
    "Chinese Super League": 70,
    "CSL": 70,
    "Primeira Liga": 62,
    "Eredivisie": 60,
}

LEAGUE_WHITELIST = {
    ("England", "Premier League"),
    ("Spain", "La Liga"),
    ("Italy", "Serie A"),
    ("Germany", "Bundesliga"),
    ("France", "Ligue 1"),
}

ELITE_CLUB_ALIASES = {
    "arsenal",
    "liverpool",
    "manchestercity",
    "mancity",
    "manchesterunited",
    "manunited",
    "realmadrid",
    "barcelona",
    "atleticomadrid",
    "inter",
    "intermilan",
    "acmilan",
    "milan",
    "juventus",
    "napoli",
    "bayernmunich",
    "bayern",
    "borussiadortmund",
    "dortmund",
    "parissaintgermain",
    "psg",
    "chelsea",
    "tottenham",
    "newcastle",
    "benfica",
    "porto",
    "sportingcp",
    "ajax",
    "psv",
}

FINISHED_STATUS_CODES = {"FT", "AET", "PEN", "CANC", "ABD", "AWD", "WO", "8"}


class ContentRouter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def route(
        self,
        fixtures: list[dict[str, Any]],
        *,
        reference_time: datetime | None = None,
    ) -> tuple[list[RoutedContentPlan], list[SelectionDecision]]:
        now = reference_time or datetime.now(timezone.utc)
        candidates: list[RoutedContentPlan] = []
        decisions: list[SelectionDecision] = []

        for fixture in fixtures:
            fixture_id = self._fixture_id(fixture)
            if fixture_id is None:
                continue

            league = self._fixture_league_name(fixture)
            league_country = self._fixture_league_country(fixture)
            kickoff = self._fixture_datetime(fixture)
            home_team = self._fixture_home_team_name(fixture)
            away_team = self._fixture_away_team_name(fixture)
            status = self._fixture_status(fixture)
            elite_fallback_allowed = self._elite_fallback_allowed(league_country, league, home_team, away_team)
            whitelist_allowed = self._league_allowed(league_country, league) or elite_fallback_allowed
            available_modes = self._available_modes(fixture, kickoff, status, now)
            base_score = self._base_score(league, home_team, away_team, fixture)

            decisions.append(
                SelectionDecision(
                    fixture_id=fixture_id,
                    selected=False,
                    score=base_score,
                    reason=f"league={league}, country={league_country}, status={status}, whitelist={whitelist_allowed}, modes={','.join(mode.value for mode in available_modes) or 'none'}",
                    metadata={
                        "league": league,
                        "league_country": league_country,
                        "home_team": home_team,
                        "away_team": away_team,
                        "status": status,
                        "whitelist_allowed": whitelist_allowed,
                        "elite_fallback_allowed": elite_fallback_allowed,
                        "available_modes": [mode.value for mode in available_modes],
                    },
                )
            )

            if not whitelist_allowed:
                continue

            for target in self.settings.content_targets:
                for mode in available_modes:
                    if mode not in target.modes:
                        continue
                    score = base_score + self._mode_bonus(mode, kickoff, now, fixture)
                    candidates.append(
                        RoutedContentPlan(
                            match_id=fixture_id,
                            platform=target.platform,
                            mode=mode,
                            account_id=target.account_id,
                            score=score,
                            priority=score,
                            reason=f"{mode.value} candidate for {target.account_id}",
                            metadata={"league": league, "home_team": home_team, "away_team": away_team},
                        )
                    )

        candidates.sort(key=lambda item: (item.score, item.match_id), reverse=True)
        plans: list[RoutedContentPlan] = []
        used_keys: set[tuple[str, int, str]] = set()
        globally_selected_matches: set[int] = set()
        target_counts = {target.account_id: 0 for target in self.settings.content_targets}
        quota_by_target = {target.account_id: target.quota for target in self.settings.content_targets}

        for pass_index in range(2):
            for candidate in candidates:
                if target_counts[candidate.account_id] >= quota_by_target.get(candidate.account_id, 0):
                    continue
                if pass_index == 0 and candidate.match_id in globally_selected_matches:
                    continue
                plan_key = (candidate.account_id, candidate.match_id, candidate.mode.value)
                if plan_key in used_keys:
                    continue
                plans.append(candidate)
                used_keys.add(plan_key)
                globally_selected_matches.add(candidate.match_id)
                target_counts[candidate.account_id] += 1

        selected_ids = {plan.match_id for plan in plans}
        for decision in decisions:
            decision.selected = decision.fixture_id in selected_ids

        return plans, decisions

    @staticmethod
    def _fixture_id(fixture: dict[str, Any]) -> int | None:
        if "fixture" in fixture:
            return fixture.get("fixture", {}).get("id")
        raw = fixture.get("id")
        return int(raw) if raw is not None else None

    @staticmethod
    def _fixture_league_name(fixture: dict[str, Any]) -> str:
        if "league" in fixture:
            return fixture.get("league", {}).get("name", "")
        return fixture.get("competition_name_en") or fixture.get("competition_name_zh") or ""

    @staticmethod
    def _fixture_league_country(fixture: dict[str, Any]) -> str:
        if "league" in fixture:
            return fixture.get("league", {}).get("country", "") or ""
        return str(fixture.get("competition_country_en") or fixture.get("competition_country_zh") or "")

    @staticmethod
    def _fixture_home_team_name(fixture: dict[str, Any]) -> str:
        if "teams" in fixture:
            return fixture.get("teams", {}).get("home", {}).get("name", "")
        return fixture.get("home_team_name_en") or fixture.get("home_team_name_zh") or ""

    @staticmethod
    def _fixture_away_team_name(fixture: dict[str, Any]) -> str:
        if "teams" in fixture:
            return fixture.get("teams", {}).get("away", {}).get("name", "")
        return fixture.get("away_team_name_en") or fixture.get("away_team_name_zh") or ""

    @staticmethod
    def _fixture_status(fixture: dict[str, Any]) -> str:
        if "fixture" in fixture:
            return fixture.get("fixture", {}).get("status", {}).get("short", "")
        status = fixture.get("status")
        return str(status) if status is not None else ""

    @staticmethod
    def _fixture_datetime(fixture: dict[str, Any]) -> datetime | None:
        try:
            if "fixture" in fixture:
                raw = fixture.get("fixture", {}).get("date")
                return datetime.fromisoformat(str(raw).replace("Z", "+00:00")) if raw else None
            raw = fixture.get("time")
            return datetime.fromtimestamp(int(raw), tz=timezone.utc) if raw else None
        except Exception:
            return None

    @classmethod
    def _base_score(cls, league: str, home_team: str, away_team: str, fixture: dict[str, Any]) -> int:
        league_score = LEAGUE_PRIORITY.get(league, 10)
        elite_bonus = 18 if cls._is_elite(home_team) or cls._is_elite(away_team) else 0
        if league_score == 10 and cls._is_elite(home_team) and cls._is_elite(away_team):
            league_score = 58
        result_bonus = cls._result_heat_bonus(fixture)
        return league_score + elite_bonus + result_bonus

    @staticmethod
    def _normalize_name(name: str | None) -> str:
        if not name:
            return ""
        return "".join(ch for ch in name.lower() if ch.isalnum())

    @staticmethod
    def _league_allowed(league_country: str, league_name: str) -> bool:
        return (league_country, league_name) in LEAGUE_WHITELIST

    @classmethod
    def _elite_fallback_allowed(cls, league_country: str, league_name: str, home_team: str, away_team: str) -> bool:
        if (league_country, league_name) in LEAGUE_WHITELIST:
            return False
        return cls._is_elite(home_team) and cls._is_elite(away_team)

    @classmethod
    def _is_elite(cls, team_name: str) -> bool:
        return cls._normalize_name(team_name) in ELITE_CLUB_ALIASES

    @staticmethod
    def _result_heat_bonus(fixture: dict[str, Any]) -> int:
        goals = fixture.get("goals") or {}
        home = goals.get("home")
        away = goals.get("away")
        if home is None or away is None:
            return 0
        margin = abs(home - away)
        total = home + away
        if margin >= 3:
            return 12
        if total >= 4:
            return 10
        if margin == 1:
            return 6
        return 4

    def _available_modes(
        self,
        fixture: dict[str, Any],
        kickoff: datetime | None,
        status: str,
        now: datetime,
    ) -> list[ContentMode]:
        del fixture
        if kickoff is None:
            return []
        delta_hours = (kickoff - now).total_seconds() / 3600
        modes: list[ContentMode] = []
        if 6 <= delta_hours <= 72 and status not in FINISHED_STATUS_CODES:
            modes.append(ContentMode.PRE_MATCH)
        if status in FINISHED_STATUS_CODES:
            age_hours = (now - kickoff).total_seconds() / 3600
            if 2 <= age_hours <= 24:
                modes.append(ContentMode.RESULT_FLASH)
            if 12 <= age_hours <= 96:
                modes.append(ContentMode.HOT_RECAP)
        return modes

    @staticmethod
    def _mode_bonus(mode: ContentMode, kickoff: datetime | None, now: datetime, fixture: dict[str, Any]) -> int:
        if kickoff is None:
            return 0
        delta_hours = (kickoff - now).total_seconds() / 3600
        if mode is ContentMode.PRE_MATCH:
            return max(0, 24 - int(abs(delta_hours - 12)))
        if mode is ContentMode.RESULT_FLASH:
            home = (fixture.get("goals") or {}).get("home")
            away = (fixture.get("goals") or {}).get("away")
            score_bonus = abs((home or 0) - (away or 0))
            return max(0, 20 - int(abs(delta_hours))) + score_bonus
        if mode is ContentMode.HOT_RECAP:
            return 8
        return 0
