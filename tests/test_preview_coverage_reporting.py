from datetime import datetime, timezone

from auto_football.config import Settings
from auto_football.db import Database
from auto_football.schemas import MatchInfo


def test_preview_payload_exposes_source_coverage_summary(tmp_path) -> None:
    settings = Settings(DATABASE_URL=f"sqlite+pysqlite:///{(tmp_path / 'preview_coverage.db').as_posix()}")
    db = Database(settings)
    db.init_db()

    db.upsert_match(
        MatchInfo(
            match_id=7201,
            league="Premier League",
            match_time=datetime(2026, 5, 6, 19, 0, tzinfo=timezone.utc),
            home_team="Liverpool",
            away_team="Arsenal",
            home_rank=2,
            away_rank=4,
            home_recent_form=["W", "W", "D", "W", "L"],
            away_recent_form=["L", "D", "W", "L", "W"],
            injuries=["Bukayo Saka: Hamstring (Doubtful)"],
            odds={"eu": {"immediate": {"win": "1.80", "draw": "3.20", "fail": "4.50"}}},
            rank_source="football_data",
            form_source="sofascore",
            knowledge_briefs=["[clubelo] Liverpool edge"],
            source_documents_count=3,
            merged_context={
                "coverage": {
                    "sources": {
                        "api_football": {"detail": True, "odds": True, "injuries": True},
                        "football_data": {"rank": True, "form": False},
                        "sofascore": {"rank": False, "form": True},
                        "clubelo": {"elo": True},
                    },
                    "total_signals": 6,
                    "ready": True,
                }
            },
        )
    )

    payload = db.get_preview_payloads(match_id=7201, limit_matches=1)[0]

    assert payload["coverage"]["ready"] is True
    assert payload["coverage"]["total_signals"] == 6
    assert payload["coverage"]["sources"]["api_football"]["odds"] is True
