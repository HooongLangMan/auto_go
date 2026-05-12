from pathlib import Path

from auto_football.clients import WhoScoredClient


def test_whoscored_stage_id_can_be_parsed_from_cached_season_html(tmp_path) -> None:
    html_path = tmp_path / "ENG-Premier League_2526.html"
    html_path.write_text(
        """
        <html>
          <body>
            <a href="/regions/252/tournaments/2/seasons/10743/stages/24533/fixtures/england-premier-league-2025-2026">Fixtures</a>
          </body>
        </html>
        """,
        encoding="utf-8",
    )

    stage_id = WhoScoredClient._extract_stage_id_from_season_html(html_path)

    assert stage_id == "24533"
