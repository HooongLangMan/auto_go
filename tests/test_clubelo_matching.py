from auto_football.clients import ClubEloClient


def test_clubelo_does_not_accept_weak_substring_false_positive() -> None:
    client = ClubEloClient.__new__(ClubEloClient)
    rankings = [
        {"Club": "Aris", "Elo": "1413.90", "Rank": "None"},
        {"Club": "Bayern", "Elo": "2008.38", "Rank": "2"},
        {"Club": "Liverpool", "Elo": "1925.09", "Rank": "9"},
    ]

    item = client.find_team("Paris Saint Germain", rankings)

    assert item is None


def test_clubelo_accepts_strong_alias_match() -> None:
    client = ClubEloClient.__new__(ClubEloClient)
    rankings = [
        {"Club": "Bayern", "Elo": "2008.38", "Rank": "2"},
        {"Club": "Liverpool", "Elo": "1925.09", "Rank": "9"},
    ]

    item = client.find_team("Bayern München", rankings)

    assert item is not None
    assert item["Club"] == "Bayern"
