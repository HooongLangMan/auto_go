from __future__ import annotations

from datetime import datetime, timedelta, timezone

from auto_football.config import Settings
from auto_football.routing import ContentRouter
from auto_football.schemas import ContentMode, Platform


def _fixture(*, fixture_id: int, league: str, country: str, home: str, away: str, kickoff: datetime, status: str, home_score: int | None = None, away_score: int | None = None) -> dict:
    return {
        "fixture": {
            "id": fixture_id,
            "date": kickoff.isoformat().replace("+00:00", "Z"),
            "status": {"short": status, "long": status},
        },
        "league": {"name": league, "country": country},
        "teams": {
            "home": {"name": home},
            "away": {"name": away},
        },
        "goals": {"home": home_score, "away": away_score},
    }


def test_router_fills_target_quotas_with_supported_modes() -> None:
    now = datetime(2026, 4, 25, 12, 0, tzinfo=timezone.utc)
    settings = Settings(
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        CONTENT_TARGETS_JSON="""
        [
          {"account_id":"wechat-main","platform":"wechat","quota":2,"modes":["pre_match","result_flash","hot_recap"]},
          {"account_id":"xhs-main","platform":"xiaohongshu","quota":1,"modes":["result_flash","hot_recap"]}
        ]
        """,
    )
    router = ContentRouter(settings)
    fixtures = [
        _fixture(
            fixture_id=101,
            league="Premier League",
            country="England",
            home="Liverpool",
            away="Arsenal",
            kickoff=now + timedelta(hours=8),
            status="NS",
        ),
        _fixture(
            fixture_id=202,
            league="La Liga",
            country="Spain",
            home="Real Madrid",
            away="Barcelona",
            kickoff=now - timedelta(hours=4),
            status="FT",
            home_score=3,
            away_score=2,
        ),
        _fixture(
            fixture_id=303,
            league="Serie A",
            country="Italy",
            home="Inter",
            away="Milan",
            kickoff=now - timedelta(hours=22),
            status="FT",
            home_score=1,
            away_score=1,
        ),
    ]

    plans, decisions = router.route(fixtures, reference_time=now)

    assert len(plans) == 3
    assert len(decisions) == 3
    assert {(plan.account_id, plan.platform) for plan in plans} == {
        ("wechat-main", Platform.WECHAT),
        ("xhs-main", Platform.XIAOHONGSHU),
    }
    assert any(plan.mode is ContentMode.PRE_MATCH and plan.match_id == 101 for plan in plans)
    assert any(plan.mode is ContentMode.RESULT_FLASH and plan.match_id == 202 for plan in plans)
    assert any(plan.mode is ContentMode.HOT_RECAP and plan.match_id == 303 for plan in plans)


def test_router_skips_non_whitelist_leagues_even_when_timing_matches() -> None:
    now = datetime(2026, 4, 25, 12, 0, tzinfo=timezone.utc)
    settings = Settings(
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        CONTENT_TARGETS_JSON="""
        [
          {"account_id":"wechat-main","platform":"wechat","quota":2,"modes":["pre_match"]},
          {"account_id":"xhs-main","platform":"xiaohongshu","quota":2,"modes":["pre_match"]}
        ]
        """,
    )
    router = ContentRouter(settings)
    fixtures = [
        _fixture(
            fixture_id=401,
            league="UEFA Champions League",
            country="World",
            home="Bayern München",
            away="Paris Saint Germain",
            kickoff=now + timedelta(hours=8),
            status="NS",
        ),
        _fixture(
            fixture_id=402,
            league="Premier League",
            country="England",
            home="Liverpool",
            away="Arsenal",
            kickoff=now + timedelta(hours=8),
            status="NS",
        ),
        {
            **_fixture(
                fixture_id=403,
                league="Premier League",
                country="England",
                home="Waterhouse",
                away="Dunbeholden",
                kickoff=now + timedelta(hours=8),
                status="NS",
            ),
            "league": {"name": "Premier League", "country": "Jamaica"},
        },
    ]

    plans, decisions = router.route(fixtures, reference_time=now)

    assert any(plan.match_id == 402 for plan in plans)
    assert all(plan.match_id != 401 for plan in plans)
    assert all(plan.match_id != 403 for plan in plans)
    ucl_decision = next(item for item in decisions if item.fixture_id == 401)
    assert ucl_decision.selected is False
    jamaica_decision = next(item for item in decisions if item.fixture_id == 403)
    assert jamaica_decision.selected is False
    assert jamaica_decision.metadata["league_country"] == "Jamaica"
