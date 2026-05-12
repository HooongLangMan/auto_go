from datetime import date
from pathlib import Path

from auto_football.clients import WhoScoredClient


def test_whoscored_cached_schedule_fixtures_promote_current_top_league_matches() -> None:
    client = WhoScoredClient.__new__(WhoScoredClient)
    client.enabled = True
    client.LEAGUE_KEYS = {"Premier League": "ENG-Premier League"}

    client._get_schedule_rows = lambda league_key, season: [
        {
            "game_id": 199001,
            "home_team": "Liverpool",
            "away_team": "Chelsea",
            "date": "2026-05-09T11:30:00Z",
            "has_preview": True,
            "home_score": None,
            "away_score": None,
        }
    ]

    fixtures = client.get_cached_schedule_fixtures(date(2026, 5, 9))

    assert len(fixtures) == 1
    fixture = fixtures[0]
    assert fixture["fixture"]["id"] == 199001
    assert fixture["league"]["name"] == "Premier League"
    assert fixture["league"]["country"] == "England"
    assert fixture["teams"]["home"]["name"] == "Liverpool"
    assert fixture["fixture"]["status"]["short"] == "NS"


def test_whoscored_refreshes_schedule_when_cache_is_empty() -> None:
    client = WhoScoredClient.__new__(WhoScoredClient)
    client.enabled = True
    client.LEAGUE_KEYS = {"Premier League": "ENG-Premier League"}

    client._get_schedule_rows = lambda league_key, season: []
    client._refresh_schedule_rows = lambda league_key, season: [
        {
            "game_id": 299001,
            "home_team": "Liverpool",
            "away_team": "Chelsea",
            "date": "2026-05-09T11:30:00Z",
            "has_preview": True,
            "home_score": None,
            "away_score": None,
        }
    ]

    fixtures = client.get_cached_schedule_fixtures(date(2026, 5, 9))

    assert len(fixtures) == 1
    assert fixtures[0]["fixture"]["id"] == 299001


def test_whoscored_match_snapshot_retries_with_targeted_refresh_when_match_missing() -> None:
    client = WhoScoredClient.__new__(WhoScoredClient)
    client.enabled = True
    client.LEAGUE_KEYS = {"Premier League": "ENG-Premier League"}

    first_rows = [
        {
            "game_id": 1903239,
            "home_team": "Chelsea",
            "away_team": "Arsenal",
            "date": "2025-11-30T16:30:00Z",
            "has_preview": True,
            "home_score": 1,
            "away_score": 1,
        }
    ]
    refreshed_rows = [
        {
            "game_id": 299002,
            "home_team": "Liverpool",
            "away_team": "Chelsea",
            "date": "2026-05-09T11:30:00Z",
            "has_preview": True,
            "home_score": None,
            "away_score": None,
        }
    ]
    calls = {"refresh": 0}
    client._get_schedule_rows = lambda league_key, season: first_rows

    def _refresh_schedule_rows_for_date(league_key, season, run_date):
        calls["refresh"] += 1
        return refreshed_rows

    client._refresh_schedule_rows_for_date = _refresh_schedule_rows_for_date
    client._get_missing_player_rows = lambda **kwargs: [
        {"team": "Liverpool", "player": "Player A", "reason": "Hamstring", "status": "Out"}
    ]

    snapshot = client.get_match_snapshot("Premier League", "Liverpool", "Chelsea", run_date=date(2026, 5, 8))

    assert calls["refresh"] == 1
    assert snapshot is not None
    assert snapshot["match_id"] == 299002


def test_whoscored_match_snapshot_uses_playwright_fallback_when_schedule_misses() -> None:
    client = WhoScoredClient.__new__(WhoScoredClient)
    client.enabled = True
    client.LEAGUE_KEYS = {"Premier League": "ENG-Premier League"}

    calls = {"refresh": 0, "playwright": 0}
    client._get_schedule_rows = lambda league_key, season: []
    client._refresh_schedule_rows_for_date = lambda league_key, season, run_date: []

    def _playwright_snapshot(league_name, home_team, away_team, run_date):
        calls["playwright"] += 1
        return {
            "home_missing": ["Alisson: injured (Out)"],
            "away_missing": ["Reece James: doubtful (Doubtful)"],
            "summary": "Liverpool missing Alisson; Chelsea missing Reece James.",
            "match_id": 399001,
            "date": "2026-05-09T11:30:00Z",
        }

    client._build_match_snapshot_via_playwright = _playwright_snapshot

    snapshot = client.get_match_snapshot("Premier League", "Liverpool", "Chelsea", run_date=date(2026, 5, 8))

    assert calls["playwright"] == 1
    assert snapshot is not None
    assert snapshot["match_id"] == 399001
    assert snapshot["home_missing"] == ["Alisson: injured (Out)"]


def test_whoscored_extracts_match_id_from_league_html() -> None:
    html = """
    <html>
      <body>
        <div class="Match-module_teams__sGVeq">
          <div class="Match-module_teamName__GoJbS"><a href="/teams/26/show/england-liverpool">Liverpool</a></div>
          <div class="Match-module_teamName__GoJbS"><a href="/teams/15/show/england-chelsea">Chelsea</a></div>
        </div>
        <a href="/matches/1903430/show/england-premier-league-2025-2026-liverpool-chelsea/#comments-panel">comments</a>
      </body>
    </html>
    """

    client = WhoScoredClient.__new__(WhoScoredClient)
    match_id = client._extract_match_id_from_league_html(html, "Liverpool", "Chelsea")

    assert match_id == 1903430
