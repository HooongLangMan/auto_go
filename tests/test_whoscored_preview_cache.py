from pathlib import Path

from auto_football.clients import WhoScoredClient


def test_whoscored_uses_cached_preview_html_when_available(tmp_path) -> None:
    preview_dir = tmp_path / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    preview_file = preview_dir / "1903211.html"
    preview_file.write_text(
        """
        <html>
          <body>
            <div id="missing-players">
              <div class="team-selector">
                <div class="home-selector selected"><span class="team-name">Liverpool</span></div>
                <div class="away-selector"><span class="team-name">Aston Villa</span></div>
              </div>
              <div class="home small-display-on">
                <table><tbody><tr><td class="pn"><a>Alisson</a></td><td class="reason"><span title="injured">Injured</span></td><td class="confirmed">Out</td></tr></tbody></table>
              </div>
              <div class="away small-display-off">
                <table><tbody><tr><td class="pn"><a>Youri Tielemans</a></td><td class="reason"><span title="injured">Injured</span></td><td class="confirmed">Out</td></tr></tbody></table>
              </div>
            </div>
          </body>
        </html>
        """,
        encoding="utf-8",
    )

    client = WhoScoredClient.__new__(WhoScoredClient)
    client.browser_path = None
    client.headless = False

    html = client._fetch_preview_html(game_id=1903211, preview_dir=preview_dir)

    assert html is not None
    assert "missing-players" in html


def test_whoscored_preview_parser_extracts_missing_players_from_html() -> None:
    html = """
    <html>
      <body>
        <div id="missing-players">
          <div class="team-selector">
            <div class="home-selector selected"><span class="team-name">Liverpool</span></div>
            <div class="away-selector"><span class="team-name">Chelsea</span></div>
          </div>
          <div class="home small-display-on">
            <table><tbody>
              <tr><td class="pn"><a>Alisson</a></td><td class="reason"><span title="injured">Injured</span></td><td class="confirmed">Out</td></tr>
            </tbody></table>
          </div>
          <div class="away small-display-off">
            <table><tbody>
              <tr><td class="pn"><a>Reece James</a></td><td class="reason"><span title="doubtful">Doubtful</span></td><td class="confirmed">Doubtful</td></tr>
            </tbody></table>
          </div>
        </div>
      </body>
    </html>
    """

    client = WhoScoredClient.__new__(WhoScoredClient)
    rows = client._parse_missing_players_html(html)
    snapshot = client._build_missing_player_snapshot("Liverpool", "Chelsea", rows)

    assert snapshot["home_missing"] == ["Alisson: injured (Out)"]
    assert snapshot["away_missing"] == ["Reece James: doubtful (Doubtful)"]
    assert "Liverpool" in snapshot["summary"]
