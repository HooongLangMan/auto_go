from datetime import datetime, timezone

from auto_football.config import Settings
from auto_football.routing import ContentRouter


def _fixture(*, fixture_id: int, league: str, country: str, home: str, away: str) -> dict:
    return {
        "fixture": {
            "id": fixture_id,
            "date": datetime(2026, 5, 6, 19, 0, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
            "status": {"short": "NS", "long": "Not Started"},
        },
        "league": {"name": league, "country": country},
        "teams": {"home": {"name": home}, "away": {"name": away}},
        "goals": {"home": None, "away": None},
    }


def test_router_rejects_league_name_collisions_outside_supported_countries() -> None:
    router = ContentRouter(Settings(DATABASE_URL="sqlite+pysqlite:///:memory:"))
    fixtures = [
        _fixture(fixture_id=8001, league="Premier League", country="England", home="Liverpool", away="Arsenal"),
        _fixture(fixture_id=8002, league="Premier League", country="Uganda", home="Lugazi", away="Mbarara City"),
        _fixture(fixture_id=8003, league="Premier League", country="Egypt", home="Haras El Hodood", away="Masr"),
    ]

    plans, decisions = router.route(fixtures, reference_time=datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc))

    selected_ids = {plan.match_id for plan in plans}
    assert 8001 in selected_ids
    assert 8002 not in selected_ids
    assert 8003 not in selected_ids
    assert next(item for item in decisions if item.fixture_id == 8002).metadata["whitelist_allowed"] is False


def test_router_rejects_world_ucl_elite_fallback_without_supported_country() -> None:
    router = ContentRouter(Settings(DATABASE_URL="sqlite+pysqlite:///:memory:"))
    fixtures = [
        _fixture(fixture_id=8010, league="UEFA UCL", country="", home="Bayern Munich", away="PSG"),
    ]

    plans, decisions = router.route(fixtures, reference_time=datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc))

    assert plans == []
    assert decisions[0].metadata["elite_fallback_allowed"] is False
