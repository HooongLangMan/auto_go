from auto_football.clients import WhoScoredClient


def test_whoscored_preview_parser_extracts_missing_players_from_html() -> None:
    html = """
    <html>
      <body>
        <div id="missing-players">
          <div class="team-selector">
            <div class="home-selector selected"><span class="team-name">Liverpool</span></div>
            <div class="away-selector"><span class="team-name">Arsenal</span></div>
          </div>
          <div class="home small-display-on">
            <table class="grid gray">
              <tbody>
                <tr>
                  <td class="pn"><a href="/Players/1/Show/Alisson">Alisson</a></td>
                  <td class="reason"><span title="injured">Injured</span></td>
                  <td class="confirmed">Out</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="away small-display-off">
            <table class="grid gray">
              <tbody>
                <tr>
                  <td class="pn"><a href="/Players/2/Show/Bukayo-Saka">Bukayo Saka</a></td>
                  <td class="reason"><span title="injured doubtful">Injured</span></td>
                  <td class="confirmed">Doubtful</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </body>
    </html>
    """

    rows = WhoScoredClient._parse_missing_players_html(html)

    assert rows == [
        {"team": "Liverpool", "player": "Alisson", "reason": "injured", "status": "Out"},
        {"team": "Arsenal", "player": "Bukayo Saka", "reason": "injured doubtful", "status": "Doubtful"},
    ]
