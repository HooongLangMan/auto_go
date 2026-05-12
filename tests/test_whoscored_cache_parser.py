import json
from pathlib import Path

from auto_football.clients import WhoScoredClient


def test_whoscored_cache_body_json_parser_extracts_payload(tmp_path) -> None:
    cache_file = tmp_path / "ENG-Premier League_2526_24533_10.json"
    payload = {
        "tournaments": [
            {
                "matches": [
                    {
                        "id": 1903207,
                        "homeTeamName": "Brighton",
                        "awayTeamName": "Leeds",
                        "startTimeUtc": "2025-11-01T15:00:00Z",
                        "hasPreview": True,
                    }
                ]
            }
        ]
    }
    cache_file.write_text(f"<html><body>{json.dumps(payload)}</body></html>", encoding="utf-8")

    parsed = WhoScoredClient._load_cached_body_json(cache_file)

    assert parsed["tournaments"][0]["matches"][0]["id"] == 1903207


def test_whoscored_schedule_rows_can_be_built_from_cached_month_payload() -> None:
    month_payload = {
        "tournaments": [
            {
                "stageId": 24533,
                "matches": [
                    {
                        "id": 1903207,
                        "homeTeamName": "Liverpool",
                        "awayTeamName": "Arsenal",
                        "startTimeUtc": "2025-11-01T15:00:00Z",
                        "hasPreview": True,
                        "homeScore": None,
                        "awayScore": None,
                    }
                ],
            }
        ]
    }

    rows = WhoScoredClient._schedule_rows_from_month_payload("ENG-Premier League", 2025, month_payload)

    assert rows[0]["game_id"] == 1903207
    assert rows[0]["home_team"] == "Liverpool"
    assert rows[0]["away_team"] == "Arsenal"
    assert rows[0]["has_preview"] is True
