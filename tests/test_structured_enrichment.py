from __future__ import annotations

from datetime import date, datetime, timezone

from auto_football.schemas import MatchInfo
from auto_football.structured_data import StructuredDataService


class FakeFootballDataClient:
    def __init__(self, snapshots: dict[str, dict]):
        self.snapshots = snapshots

    def get_team_snapshot(self, league_name: str, team_name: str, limit: int = 5) -> dict | None:
        del league_name, limit
        return self.snapshots.get(team_name)


class FakeSofascoreClient:
    def __init__(self, snapshots: dict[str, dict]):
        self.snapshots = snapshots

    def get_team_snapshot(self, league_name: str, team_name: str, season: int | None = None, limit: int = 5) -> dict | None:
        del league_name, season, limit
        return self.snapshots.get(team_name)


class FakeOpenFootballClient:
    def __init__(self, forms: dict[str, list[str]]):
        self.forms = forms

    def derive_form(self, league_name: str, team_name: str, run_date: date, limit: int = 5) -> list[str]:
        del league_name, run_date, limit
        return self.forms.get(team_name, [])


class FakeClubEloClient:
    def __init__(self, snapshots: dict[str, dict]):
        self.snapshots = snapshots

    def get_team_snapshot(self, run_date: date, team_name: str) -> dict | None:
        del run_date
        return self.snapshots.get(team_name)


def _match() -> MatchInfo:
    return MatchInfo(
        match_id=99,
        league="Premier League",
        match_time=datetime(2026, 4, 25, 20, 0, tzinfo=timezone.utc),
        home_team="Liverpool",
        away_team="Arsenal",
        must_fill=True,
    )


def test_structured_service_prefers_api_stats_when_available() -> None:
    service = StructuredDataService(
        football_data=FakeFootballDataClient(
            {
                "Liverpool": {"rank": 8, "recent_form": ["L", "L", "D"]},
                "Arsenal": {"rank": 2, "recent_form": ["W", "W", "W"]},
            }
        ),
        sofascore=FakeSofascoreClient({}),
        openfootball=FakeOpenFootballClient({}),
        clubelo=FakeClubEloClient({}),
    )

    enriched = service.enrich_match(
        _match(),
        run_date=date(2026, 4, 25),
        api_home_stats={"rank": 1, "form": ["W", "W", "D", "W", "W"]},
        api_away_stats={"rank": 3, "form": ["W", "D", "W", "W", "L"]},
    )

    assert enriched.home_rank == 1
    assert enriched.away_rank == 3
    assert enriched.home_recent_form[:3] == ["W", "W", "D"]
    assert enriched.rank_source == "api_football"
    assert enriched.form_source == "api_football"


def test_structured_service_uses_football_data_when_api_data_missing() -> None:
    service = StructuredDataService(
        football_data=FakeFootballDataClient(
            {
                "Liverpool": {"rank": 2, "recent_form": ["W", "W", "W", "D", "W"]},
                "Arsenal": {"rank": 4, "recent_form": ["L", "W", "D", "L", "W"]},
            }
        ),
        sofascore=FakeSofascoreClient({}),
        openfootball=FakeOpenFootballClient({}),
        clubelo=FakeClubEloClient({}),
    )

    enriched = service.enrich_match(_match(), run_date=date(2026, 4, 25))

    assert enriched.home_rank == 2
    assert enriched.away_rank == 4
    assert enriched.home_recent_form == ["W", "W", "W", "D", "W"]
    assert enriched.form_source == "football_data"
    assert "Liverpool" in (enriched.standings_summary or "")
    assert "Arsenal" in (enriched.form_summary or "")


def test_structured_service_uses_sofascore_when_football_data_is_missing() -> None:
    service = StructuredDataService(
        football_data=FakeFootballDataClient({}),
        sofascore=FakeSofascoreClient(
            {
                "Liverpool": {"rank": 4, "recent_form": ["W", "W", "D", "W", "L"]},
                "Arsenal": {"rank": 2, "recent_form": ["W", "D", "W", "W", "W"]},
            }
        ),
        openfootball=FakeOpenFootballClient({}),
        clubelo=FakeClubEloClient({}),
    )

    enriched = service.enrich_match(_match(), run_date=date(2026, 4, 25))

    assert enriched.home_rank == 4
    assert enriched.away_rank == 2
    assert enriched.home_recent_form == ["W", "W", "D", "W", "L"]
    assert enriched.away_recent_form == ["W", "D", "W", "W", "W"]
    assert enriched.rank_source == "sofascore"
    assert enriched.form_source == "sofascore"


def test_structured_service_uses_openfootball_form_as_fallback() -> None:
    service = StructuredDataService(
        football_data=FakeFootballDataClient(
            {
                "Liverpool": {"rank": 2, "recent_form": []},
                "Arsenal": {"rank": 4, "recent_form": []},
            }
        ),
        sofascore=FakeSofascoreClient({}),
        openfootball=FakeOpenFootballClient(
            {
                "Liverpool": ["W", "D", "W", "L", "W"],
                "Arsenal": ["L", "W", "W", "D", "D"],
            }
        ),
        clubelo=FakeClubEloClient({}),
    )

    enriched = service.enrich_match(_match(), run_date=date(2026, 4, 25))

    assert enriched.home_recent_form == ["W", "D", "W", "L", "W"]
    assert enriched.away_recent_form == ["L", "W", "W", "D", "D"]
    assert enriched.form_source == "openfootball"


def test_structured_service_keeps_clubelo_as_background_only() -> None:
    service = StructuredDataService(
        football_data=FakeFootballDataClient({}),
        sofascore=FakeSofascoreClient({}),
        openfootball=FakeOpenFootballClient({}),
        clubelo=FakeClubEloClient(
            {
                "Liverpool": {"Elo": "1910.5", "Rank": "7"},
                "Arsenal": {"Elo": "1850.0", "Rank": "14"},
            }
        ),
    )

    enriched = service.enrich_match(_match(), run_date=date(2026, 4, 25))

    assert enriched.home_rank is None
    assert enriched.away_rank is None
    assert enriched.home_elo_rank == 7
    assert enriched.away_elo_rank == 14
    assert enriched.standings_summary is not None
