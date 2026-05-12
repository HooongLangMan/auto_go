from datetime import datetime, timezone

from auto_football.config import Settings
from auto_football.db import Database
from auto_football.domain.services.content_generation_service import ContentGenerationService
from auto_football.schemas import ContentMode, ContentStatus, GeneratedContent, MatchInfo, Platform, RoutedContentPlan


def test_content_generation_prunes_stale_slice_when_match_is_now_blocked(tmp_path) -> None:
    settings = Settings(DATABASE_URL=f"sqlite+pysqlite:///{(tmp_path / 'stale_slice.db').as_posix()}")
    db = Database(settings)
    db.init_db()
    db.upsert_match(
        MatchInfo(
            match_id=7301,
            league="Premier League",
            match_time=datetime(2026, 5, 6, 19, 0, tzinfo=timezone.utc),
            home_team="Liverpool",
            away_team="Arsenal",
        )
    )
    db.save_content(
        GeneratedContent(
            match_id=7301,
            platform=Platform.WECHAT,
            mode=ContentMode.PRE_MATCH,
            account_id="wechat-main",
            status=ContentStatus.READY_TO_PUBLISH,
            title="old",
            content="old body",
        )
    )

    plan = RoutedContentPlan(
        match_id=7301,
        platform=Platform.WECHAT,
        mode=ContentMode.PRE_MATCH,
        account_id="wechat-main",
        score=1,
        priority=1,
        reason="test",
    )
    service = ContentGenerationService(db, build_candidate_pool=lambda content_plan, content_match: [])

    generated = service.generate([plan], {7301: MatchInfo(match_id=7301, league="Premier League", match_time=datetime(2026, 5, 6, 19, 0, tzinfo=timezone.utc), home_team="Liverpool", away_team="Arsenal")})

    assert generated == []
    bundle = db.get_match_bundle(7301)
    assert bundle is not None
    assert bundle["contents"] == {}
