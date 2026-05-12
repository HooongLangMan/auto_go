from __future__ import annotations

import csv
import json
import re
import unicodedata
from datetime import date, datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any, NamedTuple

import httpx
from bs4 import BeautifulSoup
from lxml import html
from tenacity import retry, stop_after_attempt, wait_exponential

from auto_football.config import Settings
from auto_football.schemas import (
    EditorialBrief,
    FactPack,
    GeneratedContent,
    MatchInfo,
    OutlineSelection,
    Platform,
    SourceDocument,
    StyleSelection,
)

try:
    from statsbombpy import sb
except Exception:  # pragma: no cover - optional dependency resilience
    sb = None


class ApiFootballClient:
    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.api_football_base_url.rstrip("/")
        self.api_key = settings.api_football_key
        self.timeout = 30.0

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def _get(self, endpoint: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        headers = {"x-apisports-key": self.api_key}
        with httpx.Client(base_url=self.base_url, timeout=self.timeout, headers=headers, follow_redirects=True) as client:
            response = client.get(endpoint, params=params)
            response.raise_for_status()
            payload = response.json()
        return payload.get("response", [])

    def get_daily_fixtures(self, run_date: date) -> list[dict[str, Any]]:
        try:
            return self._get("/fixtures", {"date": run_date.isoformat()})
        except Exception:
            return []

    def get_match_detail(self, match_id: int) -> dict[str, Any] | None:
        try:
            items = self._get("/fixtures", {"id": match_id})
        except Exception:
            return None
        return items[0] if items else None

    def get_team_stats(self, team_id: int, *, league_id: int | None = None, season: int | None = None) -> dict[str, Any] | None:
        if league_id and season:
            try:
                standings = self._get("/standings", {"league": league_id, "season": season})
            except Exception:
                standings = []
            table = standings[0]["league"]["standings"][0] if standings else []
            for row in table:
                form = [item for item in (row.get("form") or "").split("-") if item]
                if row.get("team", {}).get("id") == team_id:
                    return {"rank": row.get("rank"), "form": form, "raw": row}
        try:
            recent = self._get("/fixtures", {"team": team_id, "last": 5})
        except Exception:
            recent = []
        form = []
        for item in recent:
            goals = item.get("goals", {})
            teams = item.get("teams", {})
            home_id = teams.get("home", {}).get("id")
            away_id = teams.get("away", {}).get("id")
            home_goals = goals.get("home")
            away_goals = goals.get("away")
            if home_goals is None or away_goals is None:
                continue
            if home_id == team_id:
                form.append("W" if home_goals > away_goals else "D" if home_goals == away_goals else "L")
            elif away_id == team_id:
                form.append("W" if away_goals > home_goals else "D" if away_goals == home_goals else "L")
        return {"rank": None, "form": form, "raw": recent} if form else None

    def get_odds(self, match_id: int) -> dict[str, Any] | None:
        try:
            items = self._get("/odds", {"fixture": match_id})
        except Exception:
            return None
        return items[0] if items else None

    def get_injuries(
        self,
        team_id: int,
        *,
        fixture_id: int | None = None,
        league_id: int | None = None,
        season: int | None = None,
    ) -> list[str]:
        params: dict[str, Any] = {"team": team_id}
        if fixture_id:
            params["fixture"] = fixture_id
        if league_id:
            params["league"] = league_id
        if season:
            params["season"] = season
        try:
            items = self._get("/injuries", params)
        except Exception:
            items = []
        injuries: list[str] = []
        for item in items:
            player = item.get("player", {})
            name = player.get("name")
            reason = player.get("reason") or item.get("type")
            if name:
                injuries.append(f"{name}: {reason}" if reason else name)
        return injuries


class PublicMatchClient:
    def __init__(self, settings: Settings) -> None:
        self.api_url = settings.public_fixture_api_url
        self.timeout = 30.0

    def get_daily_matches(self, run_date: date) -> list[dict[str, Any]]:
        try:
            response = httpx.get(self.api_url, params={"time": run_date.isoformat()}, timeout=self.timeout, follow_redirects=True)
            response.raise_for_status()
            payload = response.json()
        except Exception:
            return []
        return payload.get("data") or []


class FootballDataClient:
    COMPETITION_CODES = {
        "premierleague": "PL",
        "englishpremierleague": "PL",
        "engpremierleague": "PL",
        "laliga": "PD",
        "spalaliga": "PD",
        "spanishlaliga": "PD",
        "seriea": "SA",
        "itaseriea": "SA",
        "bundesliga": "BL1",
        "gerbundesliga": "BL1",
        "ligue1": "FL1",
        "fraligue1": "FL1",
        "uefachampionsleague": "CL",
        "championsleague": "CL",
        "uefaeuropaleague": "EL",
        "europaleague": "EL",
        "chinesesuperleague": "CSL",
        "csl": "CSL",
    }

    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.football_data_api_url.rstrip("/")
        self.api_key = settings.football_data_api_key
        self.timeout = 30.0
        self._standings_cache: dict[str, list[dict[str, Any]]] = {}
        self._team_matches_cache: dict[tuple[int, int], list[dict[str, Any]]] = {}

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self.base_url)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.enabled:
            return {}
        headers = {"X-Auth-Token": self.api_key}
        with httpx.Client(base_url=self.base_url, timeout=self.timeout, follow_redirects=True, headers=headers, trust_env=False) as client:
            response = client.get(path, params=params or {})
            response.raise_for_status()
            return response.json()

    @classmethod
    def competition_code_for(cls, league_name: str) -> str | None:
        normalized = "".join(ch for ch in (league_name or "").lower() if ch.isalnum())
        return cls.COMPETITION_CODES.get(normalized)

    def get_standings(self, league_name: str) -> list[dict[str, Any]]:
        code = self.competition_code_for(league_name)
        if not code:
            return []
        if code in self._standings_cache:
            return self._standings_cache[code]
        try:
            payload = self._get(f"/competitions/{code}/standings")
        except Exception:
            return []
        standings = payload.get("standings") or []
        table = []
        for item in standings:
            if item.get("type") == "TOTAL":
                table = item.get("table") or []
                break
        if not table and standings:
            table = standings[0].get("table") or []
        self._standings_cache[code] = table
        return table

    def find_team_row(self, league_name: str, team_name: str) -> dict[str, Any] | None:
        target = OpenFootballClient._normalize_name(team_name)
        if not target:
            return None
        for row in self.get_standings(league_name):
            team = row.get("team") or {}
            names = [
                str(team.get("name") or ""),
                str(team.get("shortName") or ""),
                str(team.get("tla") or ""),
            ]
            normalized = [OpenFootballClient._normalize_name(name) for name in names if name]
            if any(
                value == target or value.startswith(target) or target.startswith(value) or target in value or value in target
                for value in normalized
                if value
            ):
                return row
        return None

    def get_team_matches(self, team_id: int, limit: int = 5) -> list[dict[str, Any]]:
        cache_key = (team_id, limit)
        if cache_key in self._team_matches_cache:
            return self._team_matches_cache[cache_key]
        try:
            payload = self._get(f"/teams/{team_id}/matches", {"status": "FINISHED", "limit": limit})
        except Exception:
            return []
        matches = payload.get("matches") or []
        self._team_matches_cache[cache_key] = matches
        return matches

    def get_recent_form(self, team_name: str, team_id: int, limit: int = 5) -> list[str]:
        matches = self.get_team_matches(team_id, limit=limit)
        target = OpenFootballClient._normalize_name(team_name)
        form: list[str] = []
        for item in matches:
            home = (item.get("homeTeam") or {}).get("name")
            away = (item.get("awayTeam") or {}).get("name")
            score = (item.get("score") or {}).get("fullTime") or {}
            home_goals = score.get("home")
            away_goals = score.get("away")
            if home_goals is None or away_goals is None:
                continue
            home_norm = OpenFootballClient._normalize_name(home)
            away_norm = OpenFootballClient._normalize_name(away)
            if home_norm == target:
                form.append("W" if home_goals > away_goals else "D" if home_goals == away_goals else "L")
            elif away_norm == target:
                form.append("W" if away_goals > home_goals else "D" if away_goals == home_goals else "L")
            if len(form) >= limit:
                break
        return form

    def get_team_snapshot(self, league_name: str, team_name: str, limit: int = 5) -> dict[str, Any] | None:
        row = self.find_team_row(league_name, team_name)
        if not row:
            return None
        team = row.get("team") or {}
        team_id = team.get("id")
        recent_form = self.get_recent_form(team_name, int(team_id), limit=limit) if team_id else []
        return {
            "rank": row.get("position"),
            "recent_form": recent_form,
            "team_id": team_id,
            "raw": row,
        }


class SofascoreClient:
    LEAGUE_KEYS = {
        "Premier League": "ENG-Premier League",
        "La Liga": "ESP-La Liga",
        "Serie A": "ITA-Serie A",
        "Bundesliga": "GER-Bundesliga",
        "Ligue 1": "FRA-Ligue 1",
    }

    def __init__(self, settings: Settings) -> None:
        self.enabled = True
        self._reader = None
        self._standings_cache: dict[tuple[str, int], list[dict[str, Any]]] = {}
        self._schedule_cache: dict[tuple[str, int], list[dict[str, Any]]] = {}

    @classmethod
    def league_key_for(cls, league_name: str) -> str | None:
        return cls.LEAGUE_KEYS.get(league_name)

    def get_team_snapshot(self, league_name: str, team_name: str, season: int | None = None, limit: int = 5) -> dict[str, Any] | None:
        league_key = self.league_key_for(league_name)
        if not league_key or season is None:
            return None
        standings = self._get_standings(league_key, season)
        schedule = self._get_schedule(league_key, season)
        target = OpenFootballClient._normalize_name(team_name)
        rank = None
        for row in standings:
            team_value = str(row.get("team") or "")
            if OpenFootballClient._normalize_name(team_value) == target:
                rank = self._safe_int(row.get("rank"))
                break
        recent_form = self._recent_form_from_schedule(schedule, team_name, limit=limit)
        if rank is None and not recent_form:
            return None
        return {"rank": rank, "recent_form": recent_form, "raw": {"standings": standings, "schedule": schedule}}

    def _reader_instance(self):
        if self._reader is not None:
            return self._reader
        try:
            import soccerdata as sd
        except Exception:
            self.enabled = False
            return None
        self._reader = sd.Sofascore
        return self._reader

    def _get_standings(self, league_key: str, season: int) -> list[dict[str, Any]]:
        cache_key = (league_key, season)
        if cache_key in self._standings_cache:
            return self._standings_cache[cache_key]
        reader_cls = self._reader_instance()
        if reader_cls is None:
            return []
        try:
            reader = reader_cls(leagues=[league_key], seasons=[season], no_store=True)
            table = reader.read_league_table().reset_index(drop=True)
        except Exception:
            return []
        rows: list[dict[str, Any]] = []
        for index, row in table.iterrows():
            rows.append({"team": row.get("team"), "rank": index + 1, "row": row.to_dict()})
        self._standings_cache[cache_key] = rows
        return rows

    def _get_schedule(self, league_key: str, season: int) -> list[dict[str, Any]]:
        cache_key = (league_key, season)
        if cache_key in self._schedule_cache:
            return self._schedule_cache[cache_key]
        reader_cls = self._reader_instance()
        if reader_cls is None:
            return []
        try:
            reader = reader_cls(leagues=[league_key], seasons=[season], no_store=True)
            schedule = reader.read_schedule().reset_index(drop=True)
        except Exception:
            return []
        rows: list[dict[str, Any]] = [row.to_dict() for _, row in schedule.iterrows()]
        self._schedule_cache[cache_key] = rows
        return rows

    def _recent_form_from_schedule(self, schedule: list[dict[str, Any]], team_name: str, *, limit: int) -> list[str]:
        target = OpenFootballClient._normalize_name(team_name)
        form: list[str] = []
        for item in reversed(schedule):
            home_name = str(item.get("home_team") or "")
            away_name = str(item.get("away_team") or "")
            home_goals = self._safe_int(item.get("home_score"))
            away_goals = self._safe_int(item.get("away_score"))
            if home_goals is None or away_goals is None:
                continue
            home_norm = OpenFootballClient._normalize_name(home_name)
            away_norm = OpenFootballClient._normalize_name(away_name)
            if home_norm == target:
                form.append("W" if home_goals > away_goals else "D" if home_goals == away_goals else "L")
            elif away_norm == target:
                form.append("W" if away_goals > home_goals else "D" if away_goals == home_goals else "L")
            if len(form) >= limit:
                break
        return form

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        try:
            return int(float(value)) if value not in (None, "", "nan") else None
        except (TypeError, ValueError):
            return None


class TheSportsDBClient:
    TEAM_NAME_ALIASES = {
        "Nott'm Forest": "Nottingham Forest",
    }

    def __init__(self, settings: Settings) -> None:
        self.api_url = settings.thesportsdb_api_url.rstrip("/")
        self.api_key = settings.thesportsdb_api_key or "123"

    @property
    def enabled(self) -> bool:
        return bool(self.api_url)

    def _endpoint(self, name: str) -> str:
        return f"{self.api_url}/{self.api_key}/{name}.php"

    def lookup_event(self, event_id: int) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        try:
            response = httpx.get(self._endpoint("lookupevent"), params={"id": event_id}, timeout=30.0, follow_redirects=True)
            response.raise_for_status()
            events = response.json().get("events") or []
        except Exception:
            return None
        return events[0] if events else None

    def search_team(self, team_name: str) -> dict[str, Any] | None:
        if not self.enabled or not team_name:
            return None
        try:
            response = httpx.get(self._endpoint("searchteams"), params={"t": team_name}, timeout=30.0, follow_redirects=True)
            response.raise_for_status()
            teams = response.json().get("teams") or []
        except Exception:
            return None
        return teams[0] if teams else None

    def get_team_artwork(self, team_name: str) -> dict[str, str]:
        team = None
        for candidate in self._team_name_candidates(team_name):
            team = self.search_team(candidate)
            if team:
                break
        if not team:
            return {}
        return {
            "badge": team.get("strBadge") or "",
            "logo": team.get("strLogo") or "",
            "fanart": team.get("strFanart1") or "",
            "banner": team.get("strBanner") or "",
        }

    @classmethod
    def _team_name_candidates(cls, team_name: str) -> list[str]:
        if not team_name:
            return []
        candidates = [team_name]
        alias = cls.TEAM_NAME_ALIASES.get(team_name)
        if alias and alias not in candidates:
            candidates.append(alias)
        return candidates


class ClubEloClient:
    TEAM_ALIASES = {
        "bayernmunchen": ["bayernmunich", "bayern"],
        "parissaintgermain": ["psg", "parissg"],
        "manchestercity": ["mancity"],
        "manchesterunited": ["manunited"],
        "intermilan": ["inter"],
        "acmilan": ["milan"],
    }

    def __init__(self, settings: Settings) -> None:
        self.api_url = settings.clubelo_api_url.rstrip("/")
        self.enabled = settings.clubelo_enabled

    def get_rankings(self, run_date: date) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        try:
            response = httpx.get(f"{self.api_url}/{run_date.isoformat()}", timeout=30.0, follow_redirects=True)
            response.raise_for_status()
        except Exception:
            return []
        reader = csv.DictReader(StringIO(response.text))
        return [row for row in reader]

    def find_team(self, team_name: str, rankings: list[dict[str, Any]]) -> dict[str, Any] | None:
        target = self._normalize_name(team_name)
        aliases = {target, *self.TEAM_ALIASES.get(target, [])}
        candidates = [(self._normalize_name(item.get("Club", "")), item) for item in rankings]
        for normalized, item in candidates:
            if normalized in aliases:
                return item
        for normalized, item in candidates:
            if not target or not normalized:
                continue
            shorter = min(len(normalized), len(target))
            longer = max(len(normalized), len(target))
            if shorter < 6:
                continue
            if longer > shorter * 2:
                continue
            if target.startswith(normalized) and normalized in aliases:
                return item
            if normalized.startswith(target):
                return item
        return None

    def build_documents(self, home_team: str, away_team: str, rankings: list[dict[str, Any]], crawled_at: datetime) -> list[SourceDocument]:
        docs: list[SourceDocument] = []
        for team_name in (home_team, away_team):
            item = self.find_team(team_name, rankings)
            if not item:
                continue
            docs.append(
                SourceDocument(
                    source="clubelo",
                    source_type="ranking",
                    team_name=team_name,
                    url=f"{self.api_url}/{item.get('From')}",
                    title=f"ClubElo ranking snapshot for {team_name}",
                    crawled_at=crawled_at,
                    summary=f"{team_name} Elo {item.get('Elo')} ranked {item.get('Rank')}",
                    content_text=f"{team_name} 当前 ClubElo 评分为 {item.get('Elo')}，排名第 {item.get('Rank')}。",
                    payload=item,
                )
            )
        return docs

    def get_team_snapshot(self, run_date: date, team_name: str) -> dict[str, Any] | None:
        rankings = self.get_rankings(run_date)
        if not rankings:
            return None
        return self.find_team(team_name, rankings)

    @staticmethod
    def _normalize_name(name: str | None) -> str:
        if not name:
            return ""
        normalized = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
        lowered = normalized.lower()
        for token in [
            " football club ",
            " futbol club ",
            " fc ",
            " cf ",
            " sc ",
            " ac ",
            " afc ",
            " ssc ",
            " rc ",
            " ca ",
            " cd ",
            " sv ",
            " bv ",
            " nk ",
            " fk ",
            " 1. ",
            " 1 ",
        ]:
            lowered = lowered.replace(token, " ")
        lowered = lowered.replace("&", " and ")
        return "".join(ch for ch in lowered if ch.isalnum())


class OpenFootballClient:
    LEAGUE_PATHS = {
        "Premier League": "en.1.json",
        "Bundesliga": "de.1.json",
        "La Liga": "es.1.json",
        "Serie A": "it.1.json",
        "Ligue 1": "fr.1.json",
    }

    def __init__(self, settings: Settings) -> None:
        self.enabled = settings.openfootball_enabled
        self.base_url = "https://raw.githubusercontent.com/openfootball/football.json/master"

    def get_league_matches(self, league_name: str, run_date: date) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        path = self.LEAGUE_PATHS.get(league_name)
        if not path:
            return []
        season_key = self._season_key(run_date)
        url = f"{self.base_url}/{season_key}/{path}"
        try:
            with httpx.Client(timeout=40.0, follow_redirects=True, trust_env=False) as client:
                response = client.get(url)
            response.raise_for_status()
            payload = response.json()
        except Exception:
            return []
        return payload.get("matches") or []

    def build_team_documents(self, league_name: str, team_name: str, run_date: date, crawled_at: datetime, limit: int = 5) -> list[SourceDocument]:
        matches = self.get_league_matches(league_name, run_date)
        if not matches:
            return []
        normalized_team = self._normalize_name(team_name)
        docs: list[SourceDocument] = []
        for item in reversed(matches):
            home = item.get("team1") or item.get("home") or {}
            away = item.get("team2") or item.get("away") or {}
            home_name = self._team_name(home)
            away_name = self._team_name(away)
            if not self._team_matches(normalized_team, home_name) and not self._team_matches(normalized_team, away_name):
                continue
            score = item.get("score") or {}
            home_goals, away_goals = self._extract_score(score, item.get("ft"))
            if home_goals is None or away_goals is None:
                continue
            docs.append(
                SourceDocument(
                    source="openfootball",
                    source_type="historical_match",
                    team_name=team_name,
                    url=f"{self.base_url}/{self._season_key(run_date)}/{self.LEAGUE_PATHS.get(league_name)}",
                    title=f"{team_name} openfootball recent match",
                    published_at=self._safe_match_datetime(item.get("date")),
                    crawled_at=crawled_at,
                    summary=f"{home_name} {home_goals}-{away_goals} {away_name}",
                    content_text=f"{team_name} 所在联赛历史赛果：{home_name} {home_goals}-{away_goals} {away_name}。",
                    payload=item,
                )
            )
            if len(docs) >= limit:
                break
        return docs

    def derive_form(self, league_name: str, team_name: str, run_date: date, limit: int = 5) -> list[str]:
        matches = self.get_league_matches(league_name, run_date)
        if not matches:
            return []
        normalized_team = self._normalize_name(team_name)
        form: list[str] = []
        for item in reversed(matches):
            home = item.get("team1") or item.get("home") or {}
            away = item.get("team2") or item.get("away") or {}
            home_name = self._team_name(home)
            away_name = self._team_name(away)
            score = item.get("score") or {}
            home_goals, away_goals = self._extract_score(score, item.get("ft"))
            if home_goals is None or away_goals is None:
                continue
            if self._team_matches(normalized_team, home_name):
                form.append("W" if home_goals > away_goals else "D" if home_goals == away_goals else "L")
            elif self._team_matches(normalized_team, away_name):
                form.append("W" if away_goals > home_goals else "D" if away_goals == home_goals else "L")
            if len(form) >= limit:
                break
        return form

    @staticmethod
    def _season_key(run_date: date) -> str:
        if run_date.month >= 7:
            return f"{run_date.year}-{str(run_date.year + 1)[-2:]}"
        return f"{run_date.year - 1}-{str(run_date.year)[-2:]}"

    @staticmethod
    def _team_name(raw: Any) -> str:
        if isinstance(raw, dict):
            return raw.get("name") or raw.get("club") or raw.get("team") or ""
        return str(raw or "")

    @staticmethod
    def _extract_score(score: Any, fallback: Any) -> tuple[int | None, int | None]:
        if isinstance(score, dict):
            for key in ("ft", "full_time", "score"):
                value = score.get(key)
                if isinstance(value, list) and len(value) >= 2:
                    return OpenFootballClient._parse_score_list(value)
            for key in ("ft", "full_time", "score"):
                value = score.get(key)
                if isinstance(value, str) and "-" in value:
                    return OpenFootballClient._parse_score(value)
                if isinstance(value, list) and len(value) >= 2:
                    return OpenFootballClient._parse_score_list(value)
        if isinstance(fallback, str) and "-" in fallback:
            return OpenFootballClient._parse_score(fallback)
        if isinstance(fallback, list) and len(fallback) >= 2:
            return OpenFootballClient._parse_score_list(fallback)
        if isinstance(score, str) and "-" in score:
            return OpenFootballClient._parse_score(score)
        return None, None

    @staticmethod
    def _parse_score(raw: str) -> tuple[int | None, int | None]:
        try:
            left, right = raw.split("-", 1)
            return int(left.strip()), int(right.strip())
        except Exception:
            return None, None

    @staticmethod
    def _parse_score_list(raw: list[Any]) -> tuple[int | None, int | None]:
        try:
            return int(raw[0]), int(raw[1])
        except Exception:
            return None, None

    @staticmethod
    def _safe_match_datetime(raw: Any) -> datetime | None:
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw)).replace(tzinfo=timezone.utc)
        except Exception:
            return None

    @staticmethod
    def _normalize_name(name: str | None) -> str:
        if not name:
            return ""
        return "".join(ch for ch in name.lower() if ch.isalnum())

    @classmethod
    def _team_matches(cls, normalized_target: str, candidate: str | None) -> bool:
        normalized_candidate = cls._normalize_name(candidate)
        if not normalized_target or not normalized_candidate:
            return False
        return (
            normalized_candidate == normalized_target
            or normalized_candidate.startswith(normalized_target)
            or normalized_target.startswith(normalized_candidate)
            or normalized_target in normalized_candidate
            or normalized_candidate in normalized_target
        )


class StatsBombOpenClient:
    def __init__(self, settings: Settings) -> None:
        self.enabled = settings.statsbomb_enabled and sb is not None
        self.competition_scan_limit = settings.statsbomb_competition_scan_limit

    def build_team_documents(self, team_name: str, crawled_at: datetime, limit: int = 5) -> list[SourceDocument]:
        if not self.enabled:
            return []
        docs: list[SourceDocument] = []
        try:
            competitions = sb.competitions()
        except Exception:
            return []
        competitions = competitions.sort_values("match_available", ascending=False).head(self.competition_scan_limit)
        for _, comp in competitions.iterrows():
            if len(docs) >= limit:
                break
            try:
                matches = sb.matches(int(comp["competition_id"]), int(comp["season_id"]))
            except Exception:
                continue
            if matches is None or matches.empty:
                continue
            subset = matches[
                (matches["home_team"].astype(str).str.lower() == team_name.lower())
                | (matches["away_team"].astype(str).str.lower() == team_name.lower())
            ].copy()
            if subset.empty:
                continue
            subset = subset.sort_values("match_date", ascending=False).head(limit - len(docs))
            for _, row in subset.iterrows():
                scoreline = f"{row.get('home_team')} {row.get('home_score')} - {row.get('away_score')} {row.get('away_team')}"
                docs.append(
                    SourceDocument(
                        source="statsbomb",
                        source_type="historical_match",
                        team_name=team_name,
                        url="https://github.com/statsbomb/open-data",
                        title=f"{team_name} historical open-data match",
                        published_at=self._safe_datetime(row.get("match_date")),
                        crawled_at=crawled_at,
                        summary=f"{scoreline} ({comp.get('competition_name')} {comp.get('season_name')})",
                        content_text=(
                            f"StatsBomb open data 历史比赛：{scoreline}，"
                            f"赛事 {comp.get('competition_name')}，赛季 {comp.get('season_name')}。"
                        ),
                        payload={key: self._json_safe(row.get(key)) for key in row.index},
                    )
                )
        return docs

    @staticmethod
    def _safe_datetime(value: Any) -> datetime | None:
        if value in (None, "", "nan"):
            return None
        try:
            return datetime.fromisoformat(str(value)).replace(tzinfo=timezone.utc)
        except Exception:
            return None

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if hasattr(value, "item"):
            try:
                return value.item()
            except Exception:
                return str(value)
        return value


class FBrefClient:
    LEAGUE_KEYS = {
        "Premier League": "ENG-Premier League",
        "La Liga": "ESP-La Liga",
        "Serie A": "ITA-Serie A",
        "Bundesliga": "GER-Bundesliga",
        "Ligue 1": "FRA-Ligue 1",
    }

    def __init__(self, settings: Settings) -> None:
        self.enabled = settings.fbref_enabled
        self.browser_path = settings.fbref_browser_path or None
        self.headless = settings.fbref_headless
        self._reader = None
        self._schedule_cache: dict[tuple[str, int], list[dict[str, Any]]] = {}

    def get_team_snapshot(self, league_name: str, team_name: str, season: int | None = None, limit: int = 5) -> dict[str, Any] | None:
        league_key = self.LEAGUE_KEYS.get(league_name)
        if not self.enabled or not league_key or season is None:
            return None
        reader_cls = self._reader_instance()
        if reader_cls is None:
            return None
        try:
            reader = reader_cls(
                leagues=[league_key],
                seasons=[season],
                no_store=True,
                path_to_browser=str(self.browser_path) if self.browser_path else None,
                headless=self.headless,
            )
            schedule = self._normalize_reader_rows(
                reader.read_team_match_stats(stat_type="schedule", team=team_name, force_cache=True).reset_index().to_dict("records")
            )
            shooting = self._normalize_reader_rows(
                reader.read_team_match_stats(stat_type="shooting", team=team_name, force_cache=True).reset_index().to_dict("records")
            )
        except Exception:
            return None

        recent_rows = self._merge_match_stat_rows(schedule, shooting, limit=limit)
        if not recent_rows:
            return None
        summary = self._summarize_team_stats(team_name, recent_rows)
        summary["raw"] = recent_rows
        return summary

    def build_team_documents(self, team_name: str, crawled_at: datetime) -> list[SourceDocument]:
        if not self.enabled:
            return []
        url = "https://fbref.com/en/"
        return [
            SourceDocument(
                source="fbref",
                source_type="site_snapshot",
                team_name=team_name,
                url=url,
                title="FBref generic snapshot",
                crawled_at=crawled_at,
                summary=f"FBref enabled for {team_name}, but no league-aware snapshot was requested.",
                content_text=f"FBref client is enabled for {team_name}.",
                payload={},
            )
        ]

    def build_match_documents(
        self,
        league_name: str,
        home_team: str,
        away_team: str,
        *,
        run_date: date,
        crawled_at: datetime,
        limit: int = 3,
    ) -> list[SourceDocument]:
        if not self.enabled:
            return []
        season = run_date.year if run_date.month >= 7 else run_date.year - 1
        docs: list[SourceDocument] = []
        for team_name in (home_team, away_team):
            snapshot = self.get_team_snapshot(league_name, team_name, season=season, limit=limit)
            if not snapshot:
                continue
            docs.append(
                SourceDocument(
                    source="fbref",
                    source_type="team_stat_snapshot",
                    team_name=team_name,
                    url="https://fbref.com/en/",
                    title=f"FBref stat snapshot for {team_name}",
                    crawled_at=crawled_at,
                    summary=snapshot["summary"],
                    content_text=snapshot["summary"],
                    payload=snapshot,
                )
            )
        return docs

    def _reader_instance(self):
        if self._reader is not None:
            return self._reader
        try:
            import soccerdata as sd
        except Exception:
            self.enabled = False
            return None
        self._reader = sd.FBref
        return self._reader

    @staticmethod
    def _merge_match_stat_rows(schedule_rows: list[dict[str, Any]], shooting_rows: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
        shooting_by_game = {str(item.get("game")): item for item in shooting_rows if item.get("game")}
        merged_rows: list[dict[str, Any]] = []
        for row in reversed(schedule_rows):
            game = str(row.get("game") or "")
            result = str(row.get("result") or "")
            if not game or not result:
                continue
            if result not in {"W", "D", "L"}:
                continue
            merged = dict(row)
            merged.update(shooting_by_game.get(game, {}))
            merged_rows.append(merged)
            if len(merged_rows) >= limit:
                break
        return merged_rows

    @staticmethod
    def _summarize_team_stats(team_name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        normalized_rows = [FBrefClient._normalize_row_dict(item) for item in rows]
        goals_for = [FBrefClient._safe_float(item.get("gf") or item.get("standard_gls")) for item in normalized_rows]
        goals_against = [FBrefClient._safe_float(item.get("ga")) for item in normalized_rows]
        xg_for = [FBrefClient._safe_float(item.get("xg")) for item in normalized_rows]
        xg_against = [FBrefClient._safe_float(item.get("xga")) for item in normalized_rows]
        shots = [FBrefClient._safe_float(item.get("sh") or item.get("standard_sh")) for item in normalized_rows]
        shots_on_target = [FBrefClient._safe_float(item.get("sot") or item.get("standard_sot")) for item in normalized_rows]
        goals_for_avg = FBrefClient._average(goals_for)
        goals_against_avg = FBrefClient._average(goals_against)
        xg_for_avg = FBrefClient._average(xg_for)
        xg_against_avg = FBrefClient._average(xg_against)
        shots_avg = FBrefClient._average(shots)
        shots_on_target_avg = FBrefClient._average(shots_on_target)
        form = [str(item.get("result") or "") for item in normalized_rows if item.get("result")]
        summary = (
            f"{team_name} recent output from FBref: average goals {goals_for_avg:.2f}, "
            f"average concessions {goals_against_avg:.2f}, xG {xg_for_avg:.2f}, xGA {xg_against_avg:.2f}, "
            f"shots {shots_avg:.2f}, shots on target {shots_on_target_avg:.2f}, recent results {'/'.join(form) or 'n/a'}."
        )
        return {
            "team": team_name,
            "summary": summary,
            "recent_form": form,
            "goals_for_avg": round(goals_for_avg, 2),
            "goals_against_avg": round(goals_against_avg, 2),
            "xg_for_avg": round(xg_for_avg, 2),
            "xg_against_avg": round(xg_against_avg, 2),
            "shots_avg": round(shots_avg, 2),
            "shots_on_target_avg": round(shots_on_target_avg, 2),
        }

    @staticmethod
    def _normalize_reader_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [FBrefClient._normalize_row_dict(row) for row in rows]

    @staticmethod
    def _normalize_row_dict(row: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for key, value in row.items():
            if isinstance(key, tuple):
                flattened = "_".join(str(part).strip() for part in key if str(part).strip()).lower()
            else:
                flattened = str(key).strip().lower().replace(" ", "_")
            normalized[flattened] = value
        return normalized

    @staticmethod
    def _average(values: list[float | None]) -> float:
        present = [value for value in values if value is not None]
        if not present:
            return 0.0
        return sum(present) / len(present)

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        try:
            return float(value) if value not in (None, "", "nan") else None
        except (TypeError, ValueError):
            return None


class WhoScoredClient:
    LEAGUE_KEYS = {
        "Premier League": "ENG-Premier League",
        "La Liga": "ESP-La Liga",
        "Serie A": "ITA-Serie A",
        "Bundesliga": "GER-Bundesliga",
        "Ligue 1": "FRA-Ligue 1",
    }

    def __init__(self, settings: Settings) -> None:
        self.enabled = settings.whoscored_enabled
        self.browser_path = settings.whoscored_browser_path or None
        self.headless = settings.whoscored_headless
        self._reader = None

    def build_match_documents(
        self,
        league_name: str,
        home_team: str,
        away_team: str,
        *,
        run_date: date,
        crawled_at: datetime,
    ) -> list[SourceDocument]:
        if not self.enabled:
            return []
        snapshot = self.get_match_snapshot(league_name, home_team, away_team, run_date=run_date)
        if not snapshot:
            return []
        return [
            SourceDocument(
                source="whoscored",
                source_type="availability",
                team_name=home_team,
                url="https://www.whoscored.com",
                title=f"WhoScored preview snapshot for {home_team} vs {away_team}",
                crawled_at=crawled_at,
                summary=snapshot["summary"],
                content_text=snapshot["summary"],
                payload=snapshot,
            )
        ]

    def get_match_snapshot(self, league_name: str, home_team: str, away_team: str, *, run_date: date) -> dict[str, Any] | None:
        league_key = self.LEAGUE_KEYS.get(league_name)
        if not self.enabled or not league_key:
            return None
        season = run_date.year if run_date.month >= 7 else run_date.year - 1
        schedule = self._get_schedule_rows(league_key, season)
        match_row = self._find_match_row(schedule, home_team, away_team)
        if not match_row:
            schedule = self._refresh_schedule_rows_for_date(league_key, season, run_date)
        match_row = self._find_match_row(schedule, home_team, away_team)
        if not match_row:
            return self._build_match_snapshot_via_playwright(league_name, home_team, away_team, run_date)
        missing = self._get_missing_player_rows(
            league_key=league_key,
            season=season,
            game_id=int(match_row["game_id"]),
            home_team=home_team,
            away_team=away_team,
        )
        snapshot = self._build_missing_player_snapshot(home_team, away_team, missing)
        snapshot["match_id"] = int(match_row["game_id"])
        snapshot["date"] = match_row.get("date")
        return snapshot

    def get_cached_schedule_fixtures(self, run_date: date) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        season = run_date.year if run_date.month >= 7 else run_date.year - 1
        fixtures: list[dict[str, Any]] = []
        for league_name, league_key in self.LEAGUE_KEYS.items():
            country = {
                "Premier League": "England",
                "La Liga": "Spain",
                "Serie A": "Italy",
                "Bundesliga": "Germany",
                "Ligue 1": "France",
            }.get(league_name, "")
            rows = self._get_schedule_rows(league_key, season)
            if not rows:
                rows = self._refresh_schedule_rows(league_key, season)
            for row in rows:
                try:
                    kickoff = datetime.fromisoformat(str(row.get("date")).replace("Z", "+00:00"))
                except Exception:
                    continue
                if abs((kickoff.date() - run_date).days) > 2:
                    continue
                home_score = row.get("home_score")
                away_score = row.get("away_score")
                finished = home_score is not None and away_score is not None
                fixtures.append(
                    {
                        "fixture": {
                            "id": int(row["game_id"]),
                            "date": kickoff.isoformat().replace("+00:00", "Z"),
                            "status": {
                                "short": "FT" if finished else "NS",
                                "long": "Finished" if finished else "Not Started",
                            },
                        },
                        "league": {"name": league_name, "country": country},
                        "teams": {
                            "home": {"name": row.get("home_team")},
                            "away": {"name": row.get("away_team")},
                        },
                        "goals": {"home": home_score, "away": away_score},
                    }
                )
        return fixtures

    def _reader_instance(self):
        if self._reader is not None:
            return self._reader
        try:
            import soccerdata as sd
        except Exception:
            self.enabled = False
            return None
        self._reader = sd.WhoScored
        return self._reader

    def _build_reader(self, league_key: str, season: int):
        reader_cls = self._reader_instance()
        if reader_cls is None:
            return None
        try:
            return reader_cls(
                leagues=[league_key],
                seasons=[season],
                no_store=False,
                path_to_browser=str(self.browser_path) if self.browser_path else None,
                headless=self.headless,
            )
        except Exception:
            return None

    def _get_schedule_rows(self, league_key: str, season: int) -> list[dict[str, Any]]:
        data_root = self._who_scored_data_root()
        data_dir = data_root / "matches"
        season_key = str(season)[-2:] + str(season + 1)[-2:]
        season_html = data_root / "seasons" / f"{league_key}_{season_key}.html"
        stage_id = self._extract_stage_id_from_season_html(season_html)
        patterns = [f"{league_key}_{season_key}_*.json"]
        if stage_id:
            patterns.insert(0, f"{league_key}_{season_key}_{stage_id}_*.json")
        rows: list[dict[str, Any]] = []
        seen_paths: set[Path] = set()
        for pattern in patterns:
            for path in sorted(data_dir.glob(pattern)):
                if path in seen_paths:
                    continue
                seen_paths.add(path)
                payload = self._load_cached_body_json(path)
                if not payload:
                    continue
                rows.extend(self._schedule_rows_from_month_payload(league_key, season, payload))
        deduped: dict[int, dict[str, Any]] = {}
        for row in rows:
            game_id = row.get("game_id")
            if game_id is not None:
                deduped[int(game_id)] = row
        return list(deduped.values())

    def _refresh_schedule_rows(self, league_key: str, season: int) -> list[dict[str, Any]]:
        reader = self._build_reader(league_key, season)
        if reader is None:
            return []
        try:
            schedule = reader.read_schedule()
            if schedule is None:
                return []
            records = schedule.reset_index().to_dict("records")
        except Exception:
            return []
        rows: list[dict[str, Any]] = []
        for row in records:
            normalized = {str(key).strip().lower().replace(" ", "_"): value for key, value in row.items()}
            game_id = normalized.get("game_id") or normalized.get("id")
            if game_id is None:
                continue
            rows.append(
                {
                    "league": league_key,
                    "season": season,
                    "game_id": int(game_id),
                    "home_team": normalized.get("home_team"),
                    "away_team": normalized.get("away_team"),
                    "date": normalized.get("date") or normalized.get("start_time_utc") or normalized.get("starttimeutc"),
                    "has_preview": bool(normalized.get("has_preview", True)),
                    "home_score": normalized.get("home_score"),
                    "away_score": normalized.get("away_score"),
                }
            )
        return rows

    def _refresh_schedule_rows_for_date(self, league_key: str, season: int, run_date: date) -> list[dict[str, Any]]:
        rows = self._refresh_schedule_rows(league_key, season)
        if not rows:
            return []
        filtered: list[dict[str, Any]] = []
        for row in rows:
            try:
                kickoff = datetime.fromisoformat(str(row.get("date")).replace("Z", "+00:00"))
            except Exception:
                continue
            if abs((kickoff.date() - run_date).days) <= 7:
                filtered.append(row)
        return filtered or rows

    def _build_match_snapshot_via_playwright(
        self, league_name: str, home_team: str, away_team: str, run_date: date
    ) -> dict[str, Any] | None:
        del run_date
        preview_dir = self._who_scored_data_root() / "previews"
        game_id = self._find_match_id_via_playwright(league_name, home_team, away_team)
        if game_id is None:
            return None
        preview_html = self._fetch_preview_html_playwright(game_id, preview_dir=preview_dir)
        if not preview_html:
            return None
        rows = self._parse_missing_players_html(preview_html)
        snapshot = self._build_missing_player_snapshot(home_team, away_team, rows)
        snapshot["match_id"] = int(game_id)
        return snapshot

    def _get_missing_player_rows(
        self,
        *,
        league_key: str,
        season: int,
        game_id: int,
        home_team: str,
        away_team: str,
    ) -> list[dict[str, Any]]:
        preview_dir = self._who_scored_data_root() / "previews"
        preview_html = self._fetch_preview_html(game_id, preview_dir=preview_dir)
        if preview_html:
            return self._parse_missing_players_html(preview_html)
        return []

    @staticmethod
    def _load_cached_body_json(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        raw = path.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"<body>(.*)</body>", raw, re.S)
        if match:
            raw = match.group(1)
        raw = raw.strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    @staticmethod
    def _schedule_rows_from_month_payload(league_key: str, season: int, payload: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for tournament in payload.get("tournaments") or []:
            for match in tournament.get("matches") or []:
                rows.append(
                    {
                        "league": league_key,
                        "season": season,
                        "game_id": match.get("id"),
                        "home_team": match.get("homeTeamName"),
                        "away_team": match.get("awayTeamName"),
                        "date": match.get("startTimeUtc"),
                        "has_preview": bool(match.get("hasPreview")),
                        "home_score": match.get("homeScore"),
                        "away_score": match.get("awayScore"),
                    }
                )
        return rows

    @staticmethod
    def _extract_stage_id_from_season_html(path: Path) -> str | None:
        if not path.exists():
            return None
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            tree = html.fromstring(text)
            hrefs = tree.xpath("//a[text()='Fixtures']/@href")
            if not hrefs:
                return None
            match = re.search(r"/stages/(\d+)/fixtures", hrefs[0])
            return match.group(1) if match else None
        except Exception:
            return None

    @staticmethod
    def _find_match_row(rows: list[dict[str, Any]], home_team: str, away_team: str) -> dict[str, Any] | None:
        home_target = OpenFootballClient._normalize_name(home_team)
        away_target = OpenFootballClient._normalize_name(away_team)
        for row in rows:
            row_home = OpenFootballClient._normalize_name(str(row.get("home_team") or ""))
            row_away = OpenFootballClient._normalize_name(str(row.get("away_team") or ""))
            if row_home == home_target and row_away == away_target:
                return row
        return None

    @staticmethod
    def _build_missing_player_snapshot(home_team: str, away_team: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        home_missing: list[str] = []
        away_missing: list[str] = []
        home_target = OpenFootballClient._normalize_name(home_team)
        away_target = OpenFootballClient._normalize_name(away_team)
        for row in rows:
            team_value = OpenFootballClient._normalize_name(str(row.get("team") or ""))
            player = str(row.get("player") or "").strip()
            reason = str(row.get("reason") or "").strip()
            status = str(row.get("status") or "").strip()
            if not player:
                continue
            entry = f"{player}: {reason} ({status})" if reason or status else player
            if team_value == home_target:
                home_missing.append(entry)
            elif team_value == away_target:
                away_missing.append(entry)
        summary_parts: list[str] = []
        if home_missing:
            summary_parts.append(f"{home_team} missing {', '.join(home_missing[:3])}")
        if away_missing:
            summary_parts.append(f"{away_team} missing {', '.join(away_missing[:3])}")
        summary = "; ".join(summary_parts) if summary_parts else f"No WhoScored missing-player notes for {home_team} vs {away_team}."
        return {
            "home_missing": home_missing,
            "away_missing": away_missing,
            "summary": summary,
        }

    @staticmethod
    def _who_scored_data_root() -> Path:
        return Path.home() / "soccerdata" / "data" / "WhoScored"

    def _fetch_preview_html(self, game_id: int, *, preview_dir: Path | None = None) -> str | None:
        preview_dir = preview_dir or (self._who_scored_data_root() / "previews")
        preview_file = preview_dir / f"{game_id}.html"
        if preview_file.exists():
            return preview_file.read_text(encoding="utf-8", errors="replace")
        if not self.browser_path:
            return None
        try:
            from seleniumbase import Driver
        except Exception:
            return None
        driver = None
        try:
            preview_dir.mkdir(parents=True, exist_ok=True)
            driver = Driver(uc=True, headless=self.headless, binary_location=self.browser_path)
            driver.get(f"https://www.whoscored.com/Matches/{game_id}/Preview")
            import time

            for _ in range(20):
                page = driver.page_source or ""
                if "missing-players" in page:
                    preview_file.write_text(page, encoding="utf-8", errors="ignore")
                    return page
                time.sleep(1)
            page = driver.page_source or None
            if page:
                preview_file.write_text(page, encoding="utf-8", errors="ignore")
            return page
        except Exception:
            return None
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

    def _fetch_preview_html_playwright(self, game_id: int, *, preview_dir: Path | None = None) -> str | None:
        preview_dir = preview_dir or (self._who_scored_data_root() / "previews")
        preview_file = preview_dir / f"{game_id}.html"
        if preview_file.exists():
            return preview_file.read_text(encoding="utf-8", errors="replace")
        if not self.browser_path:
            return None
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            return None
        preview_dir.mkdir(parents=True, exist_ok=True)
        browser = None
        page = None
        pw = None
        try:
            pw = sync_playwright().start()
            browser = pw.chromium.launch(
                executable_path=str(self.browser_path),
                headless=self.headless,
            )
            page = browser.new_page()
            page.goto(f"https://www.whoscored.com/Matches/{game_id}/Preview", wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(3000)
            html_text = page.content()
            if html_text:
                preview_file.write_text(html_text, encoding="utf-8", errors="ignore")
            return html_text
        except Exception:
            return None
        finally:
            try:
                if page is not None:
                    page.close()
            except Exception:
                pass
            try:
                if browser is not None:
                    browser.close()
            except Exception:
                pass
            try:
                if pw is not None:
                    pw.stop()
            except Exception:
                pass

    def _find_match_id_via_playwright(self, league_name: str, home_team: str, away_team: str) -> int | None:
        league_key = self.LEAGUE_KEYS.get(league_name)
        if not league_key or not self.browser_path:
            return None
        season = datetime.now(timezone.utc).year
        rows = self._get_schedule_rows(league_key, season)
        row = self._find_match_row(rows, home_team, away_team)
        if row and row.get("game_id"):
            return int(row["game_id"])
        league_html = self._fetch_league_html_playwright(league_key, season)
        if league_html:
            return self._extract_match_id_from_league_html(league_html, home_team, away_team)
        return None

    def _fetch_league_html_playwright(self, league_key: str, season: int) -> str | None:
        if not self.browser_path:
            return None
        season_key = str(season)[-2:] + str(season + 1)[-2:]
        league_file = self._who_scored_data_root() / "seasons" / f"{league_key}_{season_key}.html"
        if league_file.exists():
            return league_file.read_text(encoding="utf-8", errors="replace")
        return None

    @staticmethod
    def _extract_match_id_from_league_html(raw_html: str, home_team: str, away_team: str) -> int | None:
        home_target = OpenFootballClient._normalize_name(home_team)
        away_target = OpenFootballClient._normalize_name(away_team)
        matches = re.finditer(r'/matches/(\d+)/(?:show|live)/[^"\']+', raw_html, re.I)
        for match in matches:
            match_id = int(match.group(1))
            start = max(0, match.start() - 800)
            end = min(len(raw_html), match.end() + 800)
            window = raw_html[start:end]
            home_ok = home_target in OpenFootballClient._normalize_name(window)
            away_ok = away_target in OpenFootballClient._normalize_name(window)
            if home_ok and away_ok:
                return match_id
        return None

    @staticmethod
    def _parse_missing_players_html(raw_html: str) -> list[dict[str, Any]]:
        tree = html.fromstring(raw_html)
        sections = tree.xpath("//div[@id='missing-players']")
        if not sections:
            return []
        root = sections[0]
        home_team = "".join(root.xpath(".//div[contains(@class,'home-selector')]//span[contains(@class,'team-name')]/text()")).strip()
        away_team = "".join(root.xpath(".//div[contains(@class,'away-selector')]//span[contains(@class,'team-name')]/text()")).strip()
        rows: list[dict[str, Any]] = []
        mappings = [
            ("home", home_team),
            ("away", away_team),
        ]
        for side, team_name in mappings:
            for node in root.xpath(f".//div[contains(@class,'{side}') and contains(@class,'small-display')]//table/tbody/tr"):
                player = "".join(node.xpath(".//td[contains(@class,'pn')]/a/text()")).strip()
                reason = "".join(node.xpath(".//td[contains(@class,'reason')]/span/@title")).strip()
                status = "".join(node.xpath(".//td[contains(@class,'confirmed')]/text()")).strip()
                if not player:
                    continue
                rows.append(
                    {
                        "team": team_name,
                        "player": player,
                        "reason": reason,
                        "status": status,
                    }
                )
        return rows


class CandidatePrompt(NamedTuple):
    system_prompt: str
    user_prompt: str
    max_tokens: int


class ChatCompletionClient:
    def __init__(self, settings: Settings) -> None:
        self.chat_url = settings.llm_chat_url
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self.chat_url and self.model)

    def generate_json(self, *, system_prompt: str, user_prompt: str, max_tokens: int | None = None) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
            "response_format": {"type": "json_object"},
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        try:
            with httpx.Client(timeout=60.0, follow_redirects=True, trust_env=False) as client:
                response = client.post(self.chat_url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
            message = data["choices"][0]["message"]["content"]
            return json.loads(message)
        except Exception:
            return None

    def _build_candidate_prompt(
        self,
        *,
        pack: FactPack,
        brief: EditorialBrief,
        style: StyleSelection,
        outline: OutlineSelection,
        angle_spec=None,
    ) -> CandidatePrompt:
        system_prompt = (
            "You are a football content writer producing structured editorial brief and fact pack based pre-publication candidate copy. "
            "Use only the provided editorial brief and fact pack, and call out uncertainty when data is missing."
        )
        style_guidance = {
            StyleSelection.ANALYST: "Sound like a sharp analyst: direct, evidence-led, and calm.",
            StyleSelection.MEDIA_COMMENTARY: "Sound like a polished match columnist: fluent, readable, and slightly more vivid than a report.",
            StyleSelection.OLD_HAND: "Sound like an experienced football old hand: concise, worldly, and lightly opinionated without sounding theatrical.",
            StyleSelection.CALM_QUICKTAKE: "Sound like a short, careful quick take: compact, grounded, and low-drama.",
        }
        user_prompt = "\n".join(
            [
                "Build one planned content candidate from the structured inputs below.",
                f"Platform: {pack.platform.value}",
                f"Mode: {pack.mode.value}",
                f"Style: {style.value}",
                f"Style guidance: {style_guidance.get(style, '')}",
                "Avoid meta-writing phrases such as '对公众号读者来说', '只要结论足够明确', '这不代表...而是说...', or other template-like explanations about the act of analysis itself.",
                f"Outline: {outline.value}",
                f"WeChat candidate angle: {self._json_dumps(angle_spec.model_dump() if hasattr(angle_spec, 'model_dump') else angle_spec or {})}",
                f"Audience level: {brief.audience_level.value}",
                f"Stance: {brief.stance.value}",
                f"Primary angle: {brief.primary_angle}",
                f"Secondary angles: {self._json_dumps(brief.secondary_angles)}",
                f"Core claim: {brief.core_claim}",
                f"Supporting evidence: {self._json_dumps(brief.supporting_evidence)}",
                f"Discussion hook: {brief.discussion_hook}",
                f"Prohibited moves: {self._json_dumps(brief.prohibited_moves)}",
                f"Plain-language guidance: {self._json_dumps(brief.plain_language_guidance)}",
                f"Competition context: {self._json_dumps(pack.competition_context)}",
                f"Section rules: {self._json_dumps(pack.competition_context.get('sections') or {})}",
                f"Form signals: {self._json_dumps(pack.form_signals)}",
                f"Availability signals: {self._json_dumps(pack.availability_signals)}",
                f"Market signals: {self._json_dumps(pack.market_signals)}",
                f"Historical signals: {self._json_dumps(pack.historical_signals)}",
                f"Knowledge signals: {self._json_dumps(pack.knowledge_signals)}",
                f"Narrative hooks: {self._json_dumps(pack.narrative_hooks)}",
                f"Data gaps: {self._json_dumps([gap.model_dump() for gap in pack.data_gaps])}",
                f"Confidence: {self._json_dumps(pack.confidence.model_dump())}",
            ]
        )
        max_tokens = 1800 if pack.platform == Platform.WECHAT else 900
        return CandidatePrompt(system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=max_tokens)

    @staticmethod
    def _json_dumps(value: Any) -> str:
        return json.dumps(value, ensure_ascii=True, default=str)

    def generate_platform_content(self, match: MatchInfo, platform: Platform) -> GeneratedContent | None:
        prompts = {
            Platform.WECHAT: (
                "你是一位成熟的足球专栏作者。你的任务是：基于提供的 JSON 赛前数据，写一篇适合微信公众号发布的赛前分析文章。文章必须基于已给信息，不得编造；如果某个章节被标记为 skip，就直接省略，不要写缺失说明来占位。",
                (
                    "输出要求：\n"
                    "1. 只返回合法 JSON，包含 title 和 content。\n"
                    "2. title 要像成熟专栏标题，不要像统一模板标题，也不要夸张喊单。\n"
                    "3. content 控制在 850-1100 字。\n"
                    "4. 第一段直接给出倾向判断，并给出最关键的 1-2 个理由。\n"
                    "5. 如果 Section rules 把某个章节标成 skip，就直接省略，不要出现“当前数据未覆盖”“暂无稳定联赛排名数据”“暂无明确伤停信息”这类占位句。\n"
                    "6. 禁止写“对公众号读者来说”“只要结论足够明确”“这不代表……而是说……”这类模板化元叙述。\n\n"
                    "写法要求：\n"
                    "1. 像真正的人类作者在写专栏，不要像解释写作流程。\n"
                    "2. 段落之间自然过渡，但不要机械地给每段都上一句方法论解释。\n"
                    "3. 如果 style 是 analyst，就更简洁、证据导向；如果是 media_commentary，就更流畅、可读；如果是 old_hand，就更老练、有经验判断感，但仍然克制。\n"
                    "4. 不使用明显博彩指令词，不制造确定性神话。\n"
                    "5. 没有的数据不要硬补，也不要反复提醒读者你没有数据。\n\n"
                    "建议结构：\n"
                    "1. 开篇直接判断\n"
                    "2. 近期走势或比赛节奏\n"
                    "3. 伤停或阵容影响（如果有）\n"
                    "4. 赔率/市场和外部背景\n"
                    "5. 收束判断\n\n"
                    "待分析数据：\n"
                    f"{match.model_dump_json(indent=2)}"
                ),
                1800,
            ),
            Platform.XIAOHONGSHU: (
                "你是小红书足球博主，只能基于给定数据写争议型短内容，必须输出合法 JSON，禁止编造任何数据。",
                (
                    "请输出 title 和 content 两个字段。\n"
                    "要求：\n"
                    "1. content 控制在 200-500 字。\n"
                    "2. 结论前置，语气鲜明，但不能违规。\n"
                    "3. 必须有明确讨论点，方便评论区互动。\n"
                    "4. 禁止编造任何数据。\n"
                    "比赛数据如下：\n"
                    f"{match.model_dump_json(indent=2)}"
                ),
                900,
            ),
        }
        system_prompt, user_prompt, max_tokens = prompts[platform]
        payload = self.generate_json(system_prompt=system_prompt, user_prompt=user_prompt, max_tokens=max_tokens)
        if payload is None:
            return None
        return GeneratedContent(platform=platform, title=payload["title"], content=payload["content"])
