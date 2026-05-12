from auto_football.clients import FBrefClient


def test_fbref_merge_rows_handles_multiindex_style_column_names() -> None:
    rows = [
        {
            "game": "liverpool_arsenal_2025-08-31",
            "result": "W",
            "GF": "3",
            "GA": "1",
            "Standard_Gls": "3",
            "Standard_Sh": "15",
            "Standard_SoT": "6",
        }
    ]

    summary = FBrefClient._summarize_team_stats("Liverpool", rows)

    assert summary["goals_for_avg"] == 3.0
    assert summary["goals_against_avg"] == 1.0
    assert "shots on target" in summary["summary"]


def test_fbref_browser_path_is_passed_as_string() -> None:
    client = FBrefClient.__new__(FBrefClient)
    client.enabled = True
    client.browser_path = "D:/auto_go/tools/chrome-147/chrome-win64/chrome.exe"
    client.headless = True

    captured: dict[str, object] = {}

    class FakeReader:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def read_team_match_stats(self, **kwargs):
            raise RuntimeError("stop after init")

    client._reader_instance = lambda: FakeReader

    result = client.get_team_snapshot("Premier League", "Liverpool", season=2025, limit=3)

    assert result is None
    assert isinstance(captured["path_to_browser"], str)
