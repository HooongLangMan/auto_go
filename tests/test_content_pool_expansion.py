from datetime import datetime, timedelta, timezone

from auto_football.config import Settings
from auto_football.pipeline import AutoFootballPipeline
from auto_football.routing import ContentRouter
from auto_football.schemas import ContentMode, MatchInfo, Platform, RoutedContentPlan


def _fixture(*, fixture_id: int, league: str, country: str, home: str, away: str, kickoff: datetime, status: str, home_score: int | None = None, away_score: int | None = None) -> dict:
    return {
        "fixture": {
            "id": fixture_id,
            "date": kickoff.isoformat().replace("+00:00", "Z"),
            "status": {"short": status, "long": status},
        },
        "league": {"name": league, "country": country},
        "teams": {"home": {"name": home}, "away": {"name": away}},
        "goals": {"home": home_score, "away": away_score},
    }


def test_router_expands_time_windows_for_pre_match_result_and_recap() -> None:
    now = datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc)
    router = ContentRouter(
        Settings(
            DATABASE_URL="sqlite+pysqlite:///:memory:",
            CONTENT_TARGETS_JSON='[{"account_id":"wechat-main","platform":"wechat","quota":5,"modes":["pre_match","result_flash","hot_recap"]}]',
        )
    )
    fixtures = [
        _fixture(
            fixture_id=9101,
            league="Premier League",
            country="England",
            home="Liverpool",
            away="Chelsea",
            kickoff=now + timedelta(hours=60),
            status="NS",
        ),
        _fixture(
            fixture_id=9102,
            league="Premier League",
            country="England",
            home="Arsenal",
            away="Tottenham",
            kickoff=now - timedelta(hours=22),
            status="FT",
            home_score=2,
            away_score=1,
        ),
        _fixture(
            fixture_id=9103,
            league="Premier League",
            country="England",
            home="Manchester City",
            away="Manchester United",
            kickoff=now - timedelta(hours=80),
            status="FT",
            home_score=3,
            away_score=2,
        ),
    ]

    plans, _ = router.route(fixtures, reference_time=now)

    assert any(plan.match_id == 9101 and plan.mode is ContentMode.PRE_MATCH for plan in plans)
    assert any(plan.match_id == 9102 and plan.mode is ContentMode.RESULT_FLASH for plan in plans)
    assert any(plan.match_id == 9103 and plan.mode is ContentMode.HOT_RECAP for plan in plans)


def test_xhs_pre_match_can_generate_with_medium_signal_coverage(tmp_path) -> None:
    settings = Settings(DATABASE_URL=f"sqlite+pysqlite:///{(tmp_path / 'xhs_light_gate.db').as_posix()}", RUN_DRY=True)
    pipeline = AutoFootballPipeline(settings)
    pipeline.llm = type(
        "FakeLLM",
        (),
        {
            "_build_candidate_prompt": staticmethod(lambda **kwargs: type("Prompt", (), {"system_prompt": "s", "user_prompt": "u", "max_tokens": 200})()),
            "generate_json": staticmethod(lambda **kwargs: {"title": "短内容", "content": "结论前置，赔率和伤停都支持这场继续看主队方向。"}),
        },
    )()
    match = MatchInfo(
        match_id=9104,
        league="Premier League",
        match_time=datetime(2026, 5, 8, 20, 0, tzinfo=timezone.utc),
        home_team="Liverpool",
        away_team="Aston Villa",
        odds={"eu": {"immediate": {"win": "1.80", "draw": "3.20", "fail": "4.50"}}},
        injuries=["Alisson: injured (Out)"],
        merged_context={
            "coverage": {
                "ready": False,
                "total_signals": 2,
                "sources": {
                    "api_football": {"odds": True},
                    "whoscored": {"availability": True},
                },
            }
        },
    )
    plan = RoutedContentPlan(
        match_id=9104,
        platform=Platform.XIAOHONGSHU,
        mode=ContentMode.PRE_MATCH,
        account_id="xhs-main",
        score=90,
        priority=90,
        reason="test",
    )

    candidates = pipeline._build_candidate_pool(plan, match)

    assert len(candidates) >= 1


def test_wechat_pre_match_stays_blocked_for_same_medium_signal_coverage(tmp_path) -> None:
    settings = Settings(DATABASE_URL=f"sqlite+pysqlite:///{(tmp_path / 'wechat_strict_gate.db').as_posix()}", RUN_DRY=True)
    pipeline = AutoFootballPipeline(settings)
    match = MatchInfo(
        match_id=9105,
        league="Premier League",
        match_time=datetime(2026, 5, 8, 20, 0, tzinfo=timezone.utc),
        home_team="Liverpool",
        away_team="Aston Villa",
        odds={"eu": {"immediate": {"win": "1.80", "draw": "3.20", "fail": "4.50"}}},
        injuries=["Alisson: injured (Out)"],
        merged_context={
            "coverage": {
                "ready": False,
                "total_signals": 2,
                "sources": {
                    "api_football": {"odds": True},
                    "whoscored": {"availability": True},
                },
            }
        },
    )
    plan = RoutedContentPlan(
        match_id=9105,
        platform=Platform.WECHAT,
        mode=ContentMode.PRE_MATCH,
        account_id="wechat-main",
        score=90,
        priority=90,
        reason="test",
    )

    candidates = pipeline._build_candidate_pool(plan, match)

    assert candidates == []
