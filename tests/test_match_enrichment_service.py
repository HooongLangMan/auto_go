from __future__ import annotations

from datetime import date, datetime, timezone

from auto_football.config import Settings
from auto_football.db import Database
from auto_football.pipeline import AutoFootballPipeline
from auto_football.schemas import MatchInfo, MergedMatchContext


class FakeKnowledgeService:
    def gather(self, match: MatchInfo, run_date: date, api_snapshot: dict | None = None) -> MergedMatchContext:
        del run_date, api_snapshot
        return MergedMatchContext(
            fixture_id=match.match_id,
            api_snapshot={},
            crawler_documents=[],
            merged_payload={"knowledge_briefs": [f"{match.home_team} edge"]},
        )

    def apply_to_match(self, match: MatchInfo, context: MergedMatchContext) -> MatchInfo:
        match.knowledge_briefs = context.merged_payload.get("knowledge_briefs", [])
        match.source_documents_count = len(context.crawler_documents)
        match.merged_context = context.merged_payload
        return match


class FakeStructuredDataService:
    def enrich_match(self, match: MatchInfo, run_date: date, api_home_stats: dict | None = None, api_away_stats: dict | None = None) -> MatchInfo:
        del run_date
        if api_home_stats:
            match.home_rank = api_home_stats.get("rank")
            match.home_recent_form = api_home_stats.get("form", [])
        if api_away_stats:
            match.away_rank = api_away_stats.get("rank")
            match.away_recent_form = api_away_stats.get("form", [])
        return match


class FakeTheSportsDBClient:
    def get_team_artwork(self, team_name: str) -> dict[str, str]:
        return {
            "badge": f"https://img.example/{team_name.lower()}-badge.png",
            "logo": f"https://img.example/{team_name.lower()}-logo.png",
        }


class FakeApiFootballClient:
    enabled = True

    def __init__(self, detail: dict | None):
        self.detail = detail

    def get_match_detail(self, match_id: int) -> dict | None:
        if self.detail and match_id == self.detail["fixture"]["id"]:
            return self.detail
        return None

    def get_team_stats(self, team_id: int, *, league_id: int | None = None, season: int | None = None) -> dict | None:
        del league_id, season
        if team_id == 10:
            return {"rank": 3, "form": ["W", "W", "D"]}
        if team_id == 20:
            return {"rank": 7, "form": ["L", "D", "W"]}
        return None

    def get_injuries(self, team_id: int, *, fixture_id: int | None = None, league_id: int | None = None, season: int | None = None) -> list[str]:
        del fixture_id, league_id, season
        return [f"player-{team_id}"] if team_id == 10 else []

    def get_odds(self, match_id: int) -> dict | None:
        del match_id
        return {"eu": {"immediate": {"win": "1.80", "draw": "3.40", "fail": "4.20"}}}


def _pipeline(tmp_path, detail: dict | None) -> AutoFootballPipeline:
    db_path = tmp_path / "enrichment.db"
    settings = Settings(DATABASE_URL=f"sqlite+pysqlite:///{db_path.as_posix()}", RUN_DRY=True, PUBLISH_ENABLED=False)
    pipeline = AutoFootballPipeline(settings)
    pipeline.api_football = FakeApiFootballClient(detail)
    pipeline.the_sports_db = FakeTheSportsDBClient()
    pipeline.knowledge = FakeKnowledgeService()
    pipeline.structured_data = FakeStructuredDataService()
    return pipeline


def test_enrichment_uses_api_detail_path_and_persists_match(tmp_path) -> None:
    detail = {
        "fixture": {"id": 9101, "date": "2026-05-04T12:00:00+00:00", "status": {"short": "NS", "long": "Not Started"}},
        "league": {"id": 39, "name": "Premier League", "season": 2026},
        "teams": {
            "home": {"id": 10, "name": "Liverpool"},
            "away": {"id": 20, "name": "Arsenal"},
        },
        "goals": {"home": None, "away": None},
    }
    pipeline = _pipeline(tmp_path, detail)
    pipeline.enrichment_service.api_football = pipeline.api_football
    pipeline.enrichment_service.the_sports_db = pipeline.the_sports_db
    pipeline.enrichment_service.knowledge = pipeline.knowledge
    pipeline.enrichment_service.structured_data = pipeline.structured_data
    pipeline.public_daily_matches = []

    result = pipeline.enrichment({"run_id": 1, "selected_match_ids": [9101]})

    match = result["match_data"][9101]
    assert match.home_team == "Liverpool"
    assert match.away_team == "Arsenal"
    assert match.home_rank == 3
    assert match.away_rank == 7
    assert match.home_logo_url == "https://img.example/liverpool-badge.png"
    assert match.away_logo_url == "https://img.example/arsenal-badge.png"
    assert match.knowledge_briefs == ["Liverpool edge"]

    payload = pipeline.db.get_preview_payloads(match_id=9101, limit_matches=1)[0]
    assert payload["home_team"] == "Liverpool"
    assert payload["home_logo_url"] == "https://img.example/liverpool-badge.png"


def test_enrichment_falls_back_to_public_fixture_when_api_detail_missing(tmp_path) -> None:
    pipeline = _pipeline(tmp_path, None)
    pipeline.enrichment_service.api_football = pipeline.api_football
    pipeline.enrichment_service.the_sports_db = pipeline.the_sports_db
    pipeline.enrichment_service.knowledge = pipeline.knowledge
    pipeline.enrichment_service.structured_data = pipeline.structured_data
    pipeline.public_daily_matches = [
        {
            "id": "9102",
            "competition_name_en": "Premier League",
            "home_team_name_en": "Liverpool",
            "away_team_name_en": "Arsenal",
            "time": int(datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc).timestamp()),
            "home_team_log": "https://public.example/home.png",
            "away_team_log": "https://public.example/away.png",
            "competition_logo": "https://public.example/league.png",
            "status_str": "Not Started",
            "status": "NS",
        }
    ]

    result = pipeline.enrichment({"run_id": 1, "selected_match_ids": [9102]})

    match = result["match_data"][9102]
    assert match.home_team == "Liverpool"
    assert match.away_team == "Arsenal"
    assert match.home_logo_url == "https://public.example/home.png"
    assert match.away_logo_url == "https://public.example/away.png"
    assert match.competition_logo_url == "https://public.example/league.png"

    payload = pipeline.db.get_preview_payloads(match_id=9102, limit_matches=1)[0]
    assert payload["competition_logo_url"] == "https://public.example/league.png"
