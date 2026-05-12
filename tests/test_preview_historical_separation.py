from datetime import datetime, timezone

from auto_football.config import Settings
from auto_football.db import Database
from auto_football.schemas import MatchInfo


def test_preview_prefers_current_window_and_hides_old_validation_samples_by_default(tmp_path) -> None:
    settings = Settings(DATABASE_URL=f"sqlite+pysqlite:///{(tmp_path / 'preview_filter.db').as_posix()}")
    db = Database(settings)
    db.init_db()

    db.upsert_match(
        MatchInfo(
            match_id=8001,
            league="Premier League",
            match_time=datetime(2025, 11, 1, 20, 0, tzinfo=timezone.utc),
            home_team="Liverpool",
            away_team="Aston Villa",
        )
    )
    db.upsert_match(
        MatchInfo(
            match_id=8002,
            league="Premier League",
            match_time=datetime(2026, 5, 8, 20, 0, tzinfo=timezone.utc),
            home_team="Arsenal",
            away_team="Chelsea",
        )
    )

    payloads = db.get_preview_payloads(limit_matches=10, reference_time=datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc))

    assert [item["match_id"] for item in payloads] == [8002]
    assert payloads[0]["is_historical_sample"] is False


def test_preview_falls_back_to_historical_samples_when_no_current_matches_exist(tmp_path) -> None:
    settings = Settings(DATABASE_URL=f"sqlite+pysqlite:///{(tmp_path / 'preview_filter_fallback.db').as_posix()}")
    db = Database(settings)
    db.init_db()

    db.upsert_match(
        MatchInfo(
            match_id=8003,
            league="Premier League",
            match_time=datetime(2025, 11, 1, 20, 0, tzinfo=timezone.utc),
            home_team="Liverpool",
            away_team="Aston Villa",
        )
    )

    payloads = db.get_preview_payloads(limit_matches=10, reference_time=datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc))

    assert [item["match_id"] for item in payloads] == [8003]
    assert payloads[0]["is_historical_sample"] is True
