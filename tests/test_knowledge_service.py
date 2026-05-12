from datetime import datetime, timezone

from auto_football.knowledge import MultiSourceKnowledgeService
from auto_football.schemas import MatchInfo, MergedMatchContext, SourceDocument


def _match() -> MatchInfo:
    return MatchInfo(
        match_id=991,
        league="Premier League",
        match_time=datetime(2026, 5, 6, 19, 0, tzinfo=timezone.utc),
        home_team="Liverpool",
        away_team="Arsenal",
        home_recent_form=["W", "W", "D"],
        away_recent_form=["L", "D", "W"],
    )


def test_merge_payload_keeps_fbref_and_whoscored_summaries() -> None:
    match = _match()
    docs = [
        SourceDocument(
            source="fbref",
            source_type="team_stat_snapshot",
            team_name="Liverpool",
            summary="Liverpool recent xG edge is strong.",
            payload={"team": "Liverpool", "stat_summary": "Liverpool recent xG edge is strong."},
        ),
        SourceDocument(
            source="whoscored",
            source_type="availability",
            team_name="Arsenal",
            summary="Arsenal may miss Bukayo Saka.",
            payload={"team": "Arsenal", "player": "Bukayo Saka", "reason": "Hamstring", "status": "Doubtful"},
        ),
    ]

    merged = MultiSourceKnowledgeService._merge_payload(match, docs)

    assert merged["fbref_team_stat_summaries"]["Liverpool"] == "Liverpool recent xG edge is strong."
    assert merged["away_missing_players"] == ["Bukayo Saka: Hamstring (Doubtful)"]
    assert any("Arsenal may miss Bukayo Saka." in brief for brief in merged["knowledge_briefs"])


def test_apply_to_match_merges_external_missing_players_into_injuries() -> None:
    service = MultiSourceKnowledgeService.__new__(MultiSourceKnowledgeService)
    match = _match()
    match.injuries = ["Virgil van Dijk: Knock"]
    context = MergedMatchContext(
        fixture_id=match.match_id,
        merged_payload={
            "knowledge_briefs": ["[fbref] Liverpool recent xG edge is strong."],
            "home_missing_players": ["Alisson: Knee injury (Confirmed)"],
            "away_missing_players": ["Bukayo Saka: Hamstring (Doubtful)"],
            "fbref_team_stat_summaries": {"Liverpool": "Liverpool recent xG edge is strong."},
        },
    )

    enriched = service.apply_to_match(match, context)

    assert "Virgil van Dijk: Knock" in (enriched.injuries or [])
    assert "Alisson: Knee injury (Confirmed)" in (enriched.injuries or [])
    assert "Bukayo Saka: Hamstring (Doubtful)" in (enriched.injuries or [])
    assert enriched.merged_context is not None


def test_gather_uses_database_snapshot_before_recrawling() -> None:
    class FakeCache:
        settings = type("Settings", (), {"context_cache_ttl_seconds": 60, "source_doc_cache_ttl_seconds": 60})()

        def merged_context_key(self, fixture_id, run_date):
            return f"{fixture_id}:{run_date}"

        def get_json(self, key):
            return None

        def set_json(self, key, payload, ttl_seconds):
            return None

        def clubelo_key(self, run_date):
            return str(run_date)

    class FakeDB:
        def get_latest_context_snapshot(self, fixture_id):
            return {
                "fixture_id": fixture_id,
                "cache_key": "db-snapshot",
                "api_snapshot": {"fixture": {"id": fixture_id}},
                "merged_payload": {
                    "knowledge_briefs": ["[whoscored] Liverpool missing Alisson."],
                    "home_missing_players": ["Alisson: injured (Out)"],
                    "away_missing_players": [],
                    "coverage": {"total_signals": 3, "ready": True},
                },
                "source_documents": [
                    {
                        "source": "whoscored",
                        "source_type": "availability",
                        "team_name": "Liverpool",
                        "summary": "Liverpool missing Alisson.",
                        "content_text": "Liverpool missing Alisson.",
                        "payload": {"summary": "Liverpool missing Alisson."},
                    }
                ],
            }

    class ExplodingClient:
        enabled = False

        def __getattr__(self, name):
            raise AssertionError(f"unexpected external call: {name}")

    service = MultiSourceKnowledgeService(
        cache=FakeCache(),
        db=FakeDB(),
        clubelo=ExplodingClient(),
        openfootball=ExplodingClient(),
        statsbomb=ExplodingClient(),
        fbref=ExplodingClient(),
        whoscored=ExplodingClient(),
    )

    context = service.gather(_match(), datetime(2026, 5, 6, tzinfo=timezone.utc).date(), api_snapshot={})

    assert context.cache_key == "db-snapshot"
    assert context.merged_payload["coverage"]["ready"] is True
