from __future__ import annotations

from datetime import date, datetime, timezone

from auto_football.config import Settings
from auto_football.pipeline import AutoFootballPipeline
from auto_football.schemas import ContentStatus, MatchInfo, MergedMatchContext


def _fixture(*, fixture_id: int, home: str, away: str, kickoff: datetime) -> dict:
    return {
        "fixture": {
            "id": fixture_id,
            "date": kickoff.isoformat().replace("+00:00", "Z"),
            "status": {"short": "NS", "long": "Not Started"},
        },
        "league": {"id": 39, "name": "Premier League", "country": "England", "season": 2026},
        "teams": {
            "home": {"id": 10, "name": home},
            "away": {"id": 20, "name": away},
        },
        "goals": {"home": None, "away": None},
    }


class FakeApiFootballClient:
    def __init__(self, fixture: dict):
        self.fixture = fixture
        self.enabled = True

    def get_daily_fixtures(self, run_date: date) -> list[dict]:
        del run_date
        return [self.fixture]

    def get_match_detail(self, match_id: int) -> dict | None:
        return self.fixture if match_id == self.fixture["fixture"]["id"] else None

    def get_team_stats(self, team_id: int, *, league_id: int | None = None, season: int | None = None) -> dict | None:
        del league_id, season
        if team_id == 10:
            return {"rank": 2, "form": ["W", "W", "D", "W", "L"]}
        if team_id == 20:
            return {"rank": 6, "form": ["L", "D", "W", "L", "W"]}
        return None

    def get_odds(self, match_id: int) -> dict | None:
        del match_id
        return {"eu": {"immediate": {"win": "1.80", "draw": "3.40", "fail": "4.20"}}}

    def get_injuries(self, team_id: int, *, fixture_id: int | None = None, league_id: int | None = None, season: int | None = None) -> list[str]:
        del fixture_id, league_id, season
        return ["Forward A: knock"] if team_id == 10 else []


class FakePublicMatchClient:
    enabled = False

    def get_daily_matches(self, run_date: date) -> list[dict]:
        del run_date
        return []


class FakeTheSportsDBClient:
    def get_team_artwork(self, team_name: str) -> dict[str, str]:
        return {
            "badge": f"https://img.example/{team_name.replace(' ', '_').lower()}-badge.png",
            "logo": f"https://img.example/{team_name.replace(' ', '_').lower()}-logo.png",
        }


class FakeKnowledgeService:
    def gather(self, match: MatchInfo, run_date: date, api_snapshot: dict | None = None) -> MergedMatchContext:
        del run_date, api_snapshot
        return MergedMatchContext(
            fixture_id=match.match_id,
            api_snapshot={},
            crawler_documents=[],
            merged_payload={"knowledge_briefs": [f"{match.home_team} edge"], "coverage": {"ready": True, "total_signals": 4}},
        )

    def apply_to_match(self, match: MatchInfo, context: MergedMatchContext) -> MatchInfo:
        match.knowledge_briefs = context.merged_payload.get("knowledge_briefs", [])
        match.source_documents_count = len(context.crawler_documents)
        match.merged_context = context.merged_payload
        return match


class FakeStructuredDataService:
    def enrich_match(self, match: MatchInfo, run_date: date, api_home_stats: dict | None = None, api_away_stats: dict | None = None) -> MatchInfo:
        del run_date
        if api_home_stats:
            match.home_rank = api_home_stats.get("rank")
            match.home_recent_form = api_home_stats.get("form", [])
        if api_away_stats:
            match.away_rank = api_away_stats.get("rank")
            match.away_recent_form = api_away_stats.get("form", [])
        return match


class FakeLLMClient:
    def _build_candidate_prompt(self, *, pack, brief, style, outline, angle_spec=None):
        del pack, brief, style, outline, angle_spec
        return type("Prompt", (), {"system_prompt": "system", "user_prompt": "user", "max_tokens": 1800})()

    def generate_json(self, *, system_prompt: str, user_prompt: str, max_tokens: int | None = None):
        del system_prompt, user_prompt, max_tokens
        base = (
            "Liverpool 对阵 Arsenal，这是阶段 0 smoke baseline。"
            " 当前判断倾向主队不败，赔率与排名已经进入正文。"
        )
        return {
            "title": "Liverpool vs Arsenal",
            "content": "\n\n".join([base] * 8),
        }

    def generate_platform_content(self, match: MatchInfo, platform):
        from auto_football.schemas import GeneratedContent

        base = (
            f"{match.home_team} 对阵 {match.away_team}，这是阶段 0 smoke baseline。"
            f" 当前判断倾向主队不败，赔率与排名已经进入正文。"
        )
        if platform.value == "wechat":
            content = "\n\n".join([base] * 8)
        else:
            content = "\n\n".join([base] * 3)
        return GeneratedContent(match_id=match.match_id, platform=platform, title=f"{match.home_team} vs {match.away_team}", content=content)


class FakeImageGenerator:
    def build_assets(self, match: MatchInfo, verdict: str) -> list[str]:
        del verdict
        return [f"D:/fake/{match.match_id}_cover.png", f"D:/fake/{match.match_id}_prediction.png"]


def test_stage0_pipeline_smoke_baseline_persists_previewable_content(tmp_path) -> None:
    fixture = _fixture(
        fixture_id=7001,
        home="Liverpool",
        away="Arsenal",
        kickoff=datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc),
    )
    db_path = tmp_path / "stage0_smoke.db"
    settings = Settings(
        DATABASE_URL=f"sqlite+pysqlite:///{db_path.as_posix()}",
        RUN_DRY=True,
        PUBLISH_ENABLED=False,
        AI_IMAGE_ENABLED=False,
        CONTENT_TARGETS_JSON='[{"account_id":"wechat-main","platform":"wechat","quota":1,"modes":["pre_match"]}]',
    )
    pipeline = AutoFootballPipeline(settings)
    pipeline.api_football = FakeApiFootballClient(fixture)
    pipeline.public_match = FakePublicMatchClient()
    pipeline.the_sports_db = FakeTheSportsDBClient()
    pipeline.knowledge = FakeKnowledgeService()
    pipeline.structured_data = FakeStructuredDataService()
    pipeline.llm = FakeLLMClient()
    pipeline.image_generator = FakeImageGenerator()
    pipeline.cache.client = None
    pipeline.enrichment_service.api_football = pipeline.api_football
    pipeline.enrichment_service.the_sports_db = pipeline.the_sports_db
    pipeline.enrichment_service.knowledge = pipeline.knowledge
    pipeline.enrichment_service.structured_data = pipeline.structured_data
    pipeline.image_service.image_generator = pipeline.image_generator

    state = pipeline.run(run_date=date(2026, 5, 4))

    assert state["selected_match_ids"] == [7001]
    assert len(state["contents"]) == 1
    assert state["contents"][0].status is ContentStatus.READY_TO_PUBLISH

    payload = pipeline.db.get_preview_payloads(match_id=7001, limit_matches=1)[0]
    assert payload["match_id"] == 7001
    assert payload["home_team"] == "Liverpool"
    assert payload["away_team"] == "Arsenal"
    assert payload["contents"][0]["platform"] == "wechat"
    assert payload["contents"][0]["status"] == "ready_to_publish"
    assert payload["contents"][0]["images"] == ["D:/fake/7001_cover.png", "D:/fake/7001_prediction.png"]


def test_stage0_pipeline_smoke_baseline_marks_fallback_visual_strategy(tmp_path) -> None:
    fixture = _fixture(
        fixture_id=7011,
        home="Liverpool",
        away="Chelsea",
        kickoff=datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc),
    )
    db_path = tmp_path / "stage0_visual_strategy.db"
    settings = Settings(
        DATABASE_URL=f"sqlite+pysqlite:///{db_path.as_posix()}",
        RUN_DRY=True,
        PUBLISH_ENABLED=False,
        CONTENT_TARGETS_JSON='[{"account_id":"wechat-main","platform":"wechat","quota":1,"modes":["pre_match"]}]',
    )
    pipeline = AutoFootballPipeline(settings)
    pipeline.api_football = FakeApiFootballClient(fixture)
    pipeline.public_match = FakePublicMatchClient()
    pipeline.the_sports_db = FakeTheSportsDBClient()
    pipeline.knowledge = FakeKnowledgeService()
    pipeline.structured_data = FakeStructuredDataService()
    pipeline.llm = FakeLLMClient()
    pipeline.image_generator = FakeImageGenerator()
    pipeline.cache.client = None
    pipeline.enrichment_service.api_football = pipeline.api_football
    pipeline.enrichment_service.the_sports_db = pipeline.the_sports_db
    pipeline.enrichment_service.knowledge = pipeline.knowledge
    pipeline.enrichment_service.structured_data = pipeline.structured_data
    pipeline.image_service.image_generator = pipeline.image_generator

    state = pipeline.run(run_date=date(2026, 5, 4))

    assert state["contents"][0].editorial_metadata["visual_strategy"] == "fallback_local"
    assert state["contents"][0].editorial_metadata["image_budget_used"] == 0


def test_image_generation_preserves_backup_candidates(tmp_path) -> None:
    fixture = _fixture(
        fixture_id=7002,
        home="Liverpool",
        away="Arsenal",
        kickoff=datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc),
    )
    db_path = tmp_path / "stage0_candidates.db"
    settings = Settings(
        DATABASE_URL=f"sqlite+pysqlite:///{db_path.as_posix()}",
        RUN_DRY=True,
        PUBLISH_ENABLED=False,
        CONTENT_TARGETS_JSON='[{"account_id":"wechat-main","platform":"wechat","quota":1,"modes":["pre_match"]}]',
    )
    pipeline = AutoFootballPipeline(settings)
    pipeline.api_football = FakeApiFootballClient(fixture)
    pipeline.public_match = FakePublicMatchClient()
    pipeline.the_sports_db = FakeTheSportsDBClient()
    pipeline.knowledge = FakeKnowledgeService()
    pipeline.structured_data = FakeStructuredDataService()
    pipeline.image_generator = FakeImageGenerator()
    pipeline.cache.client = None
    pipeline.enrichment_service.api_football = pipeline.api_football
    pipeline.enrichment_service.the_sports_db = pipeline.the_sports_db
    pipeline.enrichment_service.knowledge = pipeline.knowledge
    pipeline.enrichment_service.structured_data = pipeline.structured_data
    pipeline.image_service.image_generator = pipeline.image_generator

    class TwoCandidateLLM:
        def _build_candidate_prompt(self, *, pack, brief, style, outline, angle_spec=None):
            del pack, brief, style, outline, angle_spec
            return type("Prompt", (), {"system_prompt": "system", "user_prompt": "user", "max_tokens": 1800})()

        def generate_json(self, *, system_prompt: str, user_prompt: str, max_tokens: int | None = None):
            del system_prompt, user_prompt, max_tokens
            self.calls = getattr(self, "calls", 0) + 1
            if self.calls == 1:
                return {
                    "title": "先看节奏，再看利物浦能不能把比赛压住",
                    "content": "利物浦这场先看节奏控制。\n\n如果主队把比赛带进自己熟悉的区间，不败方向就更顺。",
                }
            if self.calls == 2:
                return {
                    "title": "赔率把门槛摆在这，阿森纳得先扛住前段冲击",
                    "content": "这场先看市场和前段压力。\n\n若阿森纳扛不住开场压迫，比赛会更快向主队倾斜。",
                }
            if self.calls == 3:
                return {
                    "title": "这场真正先来的，是阿森纳要处理比赛压力",
                    "content": "这场先看压力线。\n\n谁先把比赛情绪接稳，谁才更像能留在正确方向上。",
                }
            if self.calls == 4:
                return {
                    "title": "这场别先看热闹，先看利物浦的底层强弱",
                    "content": "这场先看底层强弱。\n\n长期实力和近期走势叠在一起，主队更像能把比赛拉回自己熟悉的轨道。",
                }
            return None

        def generate_platform_content(self, match: MatchInfo, platform):
            del match, platform
            return None

    pipeline.llm = TwoCandidateLLM()

    state = pipeline.run(run_date=date(2026, 5, 4))

    assert len(state["contents"]) == 1

    payload = pipeline.db.get_preview_payloads(match_id=7002, limit_matches=1)[0]
    wechat_contents = [item for item in payload["contents"] if item["platform"] == "wechat"]

    assert len(wechat_contents) == 4
    assert {item["candidate_rank"] for item in wechat_contents} == {1, 2, 3, 4}
    for item in wechat_contents:
        assert item["images"] == ["D:/fake/7002_cover.png", "D:/fake/7002_prediction.png"]


def test_wechat_stage0_content_is_reader_safe_and_longform(tmp_path) -> None:
    fixture = _fixture(
        fixture_id=7003,
        home="Liverpool",
        away="Chelsea",
        kickoff=datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc),
    )
    db_path = tmp_path / "stage0_longform.db"
    settings = Settings(
        DATABASE_URL=f"sqlite+pysqlite:///{db_path.as_posix()}",
        RUN_DRY=True,
        PUBLISH_ENABLED=False,
        CONTENT_TARGETS_JSON='[{"account_id":"wechat-main","platform":"wechat","quota":1,"modes":["pre_match"]}]',
    )
    pipeline = AutoFootballPipeline(settings)
    pipeline.api_football = FakeApiFootballClient(fixture)
    pipeline.public_match = FakePublicMatchClient()
    pipeline.the_sports_db = FakeTheSportsDBClient()
    pipeline.knowledge = FakeKnowledgeService()
    pipeline.structured_data = FakeStructuredDataService()
    pipeline.llm = FakeLLMClient()
    pipeline.image_generator = FakeImageGenerator()
    pipeline.cache.client = None
    pipeline.enrichment_service.api_football = pipeline.api_football
    pipeline.enrichment_service.the_sports_db = pipeline.the_sports_db
    pipeline.enrichment_service.knowledge = pipeline.knowledge
    pipeline.enrichment_service.structured_data = pipeline.structured_data
    pipeline.image_service.image_generator = pipeline.image_generator

    pipeline.run(run_date=date(2026, 5, 4))

    payload = pipeline.db.get_preview_payloads(match_id=7003, limit_matches=1)[0]
    wechat_contents = [item for item in payload["contents"] if item["platform"] == "wechat"]

    assert wechat_contents
    assert len(wechat_contents[0]["content"]) >= 800
    assert "[clubelo]" not in wechat_contents[0]["content"]
    assert "[openfootball]" not in wechat_contents[0]["content"]
    assert "待补充" not in wechat_contents[0]["content"]
