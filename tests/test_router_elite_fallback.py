from datetime import datetime, timedelta, timezone

from auto_football.config import Settings
from auto_football.routing import ContentRouter


def _fixture(*, fixture_id: int, league: str, country: str, home: str, away: str, kickoff: datetime) -> dict:
    return {
        "fixture": {
            "id": fixture_id,
            "date": kickoff.isoformat().replace("+00:00", "Z"),
            "status": {"short": "NS", "long": "Not Started"},
        },
        "league": {"name": league, "country": country},
        "teams": {"home": {"name": home}, "away": {"name": away}},
        "goals": {"home": None, "away": None},
    }


def test_router_can_fallback_to_elite_match_when_no_top_league_fixture_exists() -> None:
    now = datetime(2026, 5, 6, 12, 0, tzinfo=timezone.utc)
    router = ContentRouter(
        Settings(
            DATABASE_URL="sqlite+pysqlite:///:memory:",
            CONTENT_TARGETS_JSON='[{"account_id":"wechat-main","platform":"wechat","quota":1,"modes":["pre_match"]}]',
        )
    )
    fixtures = [
        _fixture(
            fixture_id=9901,
            league="Primeira Liga",
            country="Portugal",
            home="Benfica",
            away="Porto",
            kickoff=now + timedelta(hours=8),
        ),
        _fixture(
            fixture_id=9902,
            league="Eredivisie",
            country="Netherlands",
            home="Ajax",
            away="PSV",
            kickoff=now + timedelta(hours=9),
        ),
    ]

    plans, decisions = router.route(fixtures, reference_time=now)

    assert {plan.match_id for plan in plans} == {9901}
    elite_decision = next(item for item in decisions if item.fixture_id == 9901)
    assert elite_decision.metadata["elite_fallback_allowed"] is True
