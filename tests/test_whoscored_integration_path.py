from datetime import date, datetime, timezone

from auto_football.config import Settings
from auto_football.knowledge import MultiSourceKnowledgeService
from auto_football.schemas import MatchInfo


class FakeCache:
    settings = type("Settings", (), {"context_cache_ttl_seconds": 60, "source_doc_cache_ttl_seconds": 60})()

    def merged_context_key(self, fixture_id, run_date):
        return f"{fixture_id}:{run_date}"

    def get_json(self, key):
        return None

    def set_json(self, key, value, ttl_seconds):
        return None

    def clubelo_key(self, run_date):
        return str(run_date)


class FakeClubElo:
    def get_rankings(self, run_date):
        return []

    def build_documents(self, home_team, away_team, rankings, crawled_at):
        return []


class FakeOpenFootball:
    enabled = False

    def build_team_documents(self, league_name, team_name, run_date, crawled_at):
        return []


class FakeStatsBomb:
    def build_team_documents(self, team_name, crawled_at):
        return []


class FakeFBref:
    def build_team_documents(self, team_name, crawled_at):
        return []

    def build_match_documents(self, league_name, home_team, away_team, *, run_date, crawled_at):
        return []


class FakeWhoScored:
    def build_match_documents(self, league_name, home_team, away_team, *, run_date, crawled_at):
        from auto_football.schemas import SourceDocument

        return [
            SourceDocument(
                source="whoscored",
                source_type="availability",
                team_name=home_team,
                summary="Liverpool missing Alisson; Aston Villa missing Tielemans.",
                content_text="Liverpool missing Alisson; Aston Villa missing Tielemans.",
                payload={
                    "home_missing": ["Alisson: injured (Out)"],
                    "away_missing": ["Youri Tielemans: injured (Out)"],
                    "summary": "Liverpool missing Alisson; Aston Villa missing Tielemans.",
                },
            )
        ]


def test_whoscored_documents_raise_coverage_and_injuries() -> None:
    service = MultiSourceKnowledgeService(
        cache=FakeCache(),
        db=None,
        clubelo=FakeClubElo(),
        openfootball=FakeOpenFootball(),
        statsbomb=FakeStatsBomb(),
        fbref=FakeFBref(),
        whoscored=FakeWhoScored(),
    )
    match = MatchInfo(
        match_id=7401,
        league="Premier League",
        match_time=datetime(2025, 11, 1, 20, 0, tzinfo=timezone.utc),
        home_team="Liverpool",
        away_team="Aston Villa",
        odds={"eu": {"immediate": {"win": "1.80", "draw": "3.20", "fail": "4.50"}}},
    )

    context = service.gather(match, date(2025, 11, 1), api_snapshot={"fixture": {"id": 7401}})
    enriched = service.apply_to_match(match, context)

    assert "Alisson: injured (Out)" in (enriched.injuries or [])
    assert enriched.external_availability_summary is not None
    assert (enriched.merged_context or {}).get("coverage", {}).get("total_signals", 0) >= 2
