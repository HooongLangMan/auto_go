from __future__ import annotations

from auto_football.clients import TheSportsDBClient
from auto_football.config import Settings


def test_get_team_artwork_retries_common_abbreviated_team_name(monkeypatch) -> None:
    client = TheSportsDBClient(Settings())
    seen: list[str] = []

    def fake_search_team(team_name: str):
        seen.append(team_name)
        if team_name == "Nott'm Forest":
            return None
        if team_name == "Nottingham Forest":
            return {
                "strBadge": "https://example.com/forest-badge.png",
                "strLogo": "https://example.com/forest-logo.png",
                "strFanart1": "",
                "strBanner": "",
            }
        return None

    monkeypatch.setattr(client, "search_team", fake_search_team)

    artwork = client.get_team_artwork("Nott'm Forest")

    assert artwork["badge"] == "https://example.com/forest-badge.png"
    assert seen == ["Nott'm Forest", "Nottingham Forest"]
