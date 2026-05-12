from datetime import datetime, timezone

from auto_football.clients import FBrefClient, WhoScoredClient


def test_fbref_client_summarizes_recent_team_stats() -> None:
    client = FBrefClient.__new__(FBrefClient)

    summary = client._summarize_team_stats(
        "Liverpool",
        [
            {"gf": 2, "ga": 1, "xg": 1.8, "xga": 0.7, "sh": 14, "sot": 6},
            {"gf": 3, "ga": 1, "xg": 2.1, "xga": 0.9, "sh": 17, "sot": 7},
            {"gf": 1, "ga": 0, "xg": 1.4, "xga": 0.5, "sh": 12, "sot": 4},
        ],
    )

    assert "Liverpool" in summary["summary"]
    assert "xG" in summary["summary"]
    assert "shots on target" in summary["summary"]
    assert summary["goals_for_avg"] == 2.0
    assert summary["goals_against_avg"] == 0.67
    assert summary["xg_for_avg"] == 1.77
    assert summary["xg_against_avg"] == 0.7


def test_whoscored_client_summarizes_missing_players() -> None:
    client = WhoScoredClient.__new__(WhoScoredClient)

    snapshot = client._build_missing_player_snapshot(
        home_team="Liverpool",
        away_team="Arsenal",
        rows=[
            {"team": "Liverpool", "player": "Alisson", "reason": "Knee injury", "status": "Confirmed"},
            {"team": "Arsenal", "player": "Bukayo Saka", "reason": "Hamstring", "status": "Doubtful"},
            {"team": "Arsenal", "player": "Gabriel", "reason": "Suspended", "status": "Confirmed"},
        ],
    )

    assert snapshot["home_missing"] == ["Alisson: Knee injury (Confirmed)"]
    assert "Bukayo Saka: Hamstring (Doubtful)" in snapshot["away_missing"]
    assert "Gabriel: Suspended (Confirmed)" in snapshot["away_missing"]
    assert "Liverpool" in snapshot["summary"]
    assert "Arsenal" in snapshot["summary"]
