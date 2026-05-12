from datetime import datetime, timezone

from auto_football.config import Settings
from auto_football.pipeline import AutoFootballPipeline
from auto_football.schemas import (
    ContentMode,
    ContentReadiness,
    EditorialStance,
    GeneratedContent,
    MatchInfo,
    OutlineSelection,
    Platform,
    RoutedContentPlan,
    StyleSelection,
)


def test_pipeline_content_generation_selects_ranked_top_candidate(tmp_path) -> None:
    settings = Settings(DATABASE_URL=f"sqlite+pysqlite:///{(tmp_path / 'content_engine.db').as_posix()}", RUN_DRY=True)
    pipeline = AutoFootballPipeline(settings)
    match = MatchInfo(
        match_id=6001,
        league="Premier League",
        match_time=datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc),
        home_team="Liverpool",
        away_team="Arsenal",
        home_recent_form=["W", "W", "D", "W", "L"],
        away_recent_form=["L", "D", "W", "L", "W"],
    )
    pipeline.db.upsert_match(match)
    plan = RoutedContentPlan(
        match_id=6001,
        platform=Platform.WECHAT,
        mode=ContentMode.PRE_MATCH,
        account_id="wechat-main",
        score=100,
        priority=100,
        reason="test",
    )
    pipeline.content_service.build_candidate_pool = lambda content_plan, content_match: [
        GeneratedContent(platform=content_plan.platform, title="top", content="top body"),
        GeneratedContent(platform=content_plan.platform, title="backup", content="backup body"),
    ]

    contents = pipeline.content_service.generate([plan], {6001: match})

    assert len(contents) == 1
    assert contents[0].title == "top"
    assert contents[0].candidate_rank == 1
    assert contents[0].candidate_count == 2


def test_pre_match_candidate_pool_runs_through_editorial_services(tmp_path) -> None:
    settings = Settings(DATABASE_URL=f"sqlite+pysqlite:///{(tmp_path / 'pre_match_engine.db').as_posix()}", RUN_DRY=True)
    pipeline = AutoFootballPipeline(settings)
    match = MatchInfo(
        match_id=6002,
        league="Premier League",
        match_time=datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc),
        home_team="Liverpool",
        away_team="Arsenal",
        home_recent_form=["W", "W", "D", "W", "L"],
        away_recent_form=["L", "D", "W", "L", "W"],
        home_rank=2,
        away_rank=5,
        form_summary="Home form is stronger.",
        standings_summary="Home side is chasing the title while away side is chasing Europe.",
        knowledge_briefs=["[clubelo] Home side has the stronger long-term profile."],
        merged_context={"coverage": {"ready": True, "total_signals": 4}},
    )
    plan = RoutedContentPlan(
        match_id=6002,
        platform=Platform.WECHAT,
        mode=ContentMode.PRE_MATCH,
        account_id="wechat-main",
        score=100,
        priority=100,
        reason="test",
    )

    captured: dict[str, object] = {}

    class FakeFactPackService:
        def build(self, content_match, content_plan):
            captured["fact_match_id"] = content_match.match_id
            captured["fact_plan_mode"] = content_plan.mode
            from auto_football.schemas import FactBlockConfidence, FactPack

            return FactPack(
                match_id=content_match.match_id,
                platform=content_plan.platform,
                mode=content_plan.mode,
                readiness=ContentReadiness.HIGH,
                competition_context={"summary": "Home side chasing title"},
                form_signals={"summary": "Home form stronger"},
                availability_signals={"summary": "No major absences"},
                market_signals={"summary": "Home win shortest"},
                historical_signals={"summary": "Home unbeaten in last three meetings"},
                knowledge_signals={"language_goal": "Write for mainstream readers"},
                narrative_hooks=["table pressure"],
                data_gaps=[],
                confidence=FactBlockConfidence(overall=0.88, block_scores={"form_signals": 0.9}),
            )

    class FakeEditorialBriefService:
        def build(self, pack):
            captured["brief_readiness"] = pack.readiness
            from auto_football.schemas import AudienceLevel, EditorialBrief

            return EditorialBrief(
                platform=pack.platform,
                mode=pack.mode,
                audience_level=AudienceLevel.MAINSTREAM,
                stance=EditorialStance.BALANCED,
                primary_angle="table pressure",
                secondary_angles=["home form"],
                core_claim="Home side is less likely to lose",
                supporting_evidence=["Home form stronger"],
                discussion_hook="",
                prohibited_moves=["Do not overstate certainty."],
                plain_language_guidance=["Keep the analysis easy to follow."],
            )

    class FakeStyleRouterService:
        def choose(self, pack, brief, recent_styles=None):
            captured["style_brief_stance"] = brief.stance
            return StyleSelection.ANALYST

    class FakeOutlinePlannerService:
        def choose(self, pack, brief, style, recent_pairs=None):
            captured["outline_style"] = style
            return OutlineSelection.VERDICT_FIRST

    class FakeValidator:
        def evaluate(self, content, *, pack, brief_stance, recent_openings):
            captured.setdefault("validated_titles", []).append(content.title)
            from auto_football.schemas import CandidateEvaluation

            return CandidateEvaluation(
                plain_language_score=0.95 if content.title == "Winner" else 0.7,
                fact_coverage_score=0.9 if content.title == "Winner" else 0.6,
                platform_fit_score=0.9,
                repetition_penalty=0.0,
                overall_score=0.92 if content.title == "Winner" else 0.68,
                review_summary="ok",
                hard_fail=False,
            )

    class FakeRanker:
        def rank(self, candidates):
            return sorted(candidates, key=lambda item: -item[1].overall_score)

    class FakeLLM:
        def _build_candidate_prompt(self, *, pack, brief, style, outline, angle_spec=None):
            captured["prompt_style"] = style
            captured["prompt_outline"] = outline
            captured.setdefault("angles", []).append(angle_spec)
            return type("Prompt", (), {"system_prompt": "s", "user_prompt": "u", "max_tokens": 1800})()

        def generate_json(self, *, system_prompt, user_prompt, max_tokens=None):
            captured.setdefault("llm_calls", 0)
            captured["llm_calls"] += 1
            if captured["llm_calls"] == 1:
                return {"title": "Winner", "content": "Home side looks steadier and the title pressure matters."}
            return {"title": "Backup", "content": "Away side still has some routes into the game."}

    pipeline.fact_pack_service = FakeFactPackService()
    pipeline.editorial_brief_service = FakeEditorialBriefService()
    pipeline.style_router_service = FakeStyleRouterService()
    pipeline.outline_planner_service = FakeOutlinePlannerService()
    pipeline.content_validation_service = FakeValidator()
    pipeline.candidate_ranking_service = FakeRanker()
    pipeline.llm = FakeLLM()

    candidate_pool = pipeline._build_candidate_pool(plan, match)

    assert candidate_pool[0].title == "Winner"
    assert "Backup" in [item.title for item in candidate_pool]
    assert captured["fact_match_id"] == 6002
    assert captured["fact_plan_mode"] is ContentMode.PRE_MATCH
    assert captured["brief_readiness"] is ContentReadiness.HIGH
    assert captured["style_brief_stance"] is EditorialStance.BALANCED
    assert captured["outline_style"] is StyleSelection.ANALYST
    assert captured["prompt_style"] is StyleSelection.ANALYST
    assert captured["prompt_outline"] is OutlineSelection.VERDICT_FIRST
    assert captured["validated_titles"][0] == "Winner"
    assert "Backup" in captured["validated_titles"]


def test_wechat_pre_match_candidate_pool_uses_distinct_editorial_angles(tmp_path) -> None:
    settings = Settings(DATABASE_URL=f"sqlite+pysqlite:///{(tmp_path / 'wechat_angle_pool.db').as_posix()}", RUN_DRY=True)
    pipeline = AutoFootballPipeline(settings)
    match = MatchInfo(
        match_id=6012,
        league="Premier League",
        match_time=datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc),
        home_team="Liverpool",
        away_team="Chelsea",
        home_recent_form=["L", "W", "W", "W", "L"],
        away_recent_form=["L", "L", "L", "L", "L"],
        home_elo=1925.1,
        away_elo=1827.9,
        odds={"eu": {"immediate": {"win": "1.84", "draw": "3.95", "fail": "3.65"}}},
        form_summary="Liverpool recent trend is steadier while Chelsea are sliding.",
        standings_summary="Liverpool are still carrying the bigger top-end expectation into this round.",
        knowledge_briefs=["[clubelo] Liverpool long-term strength remains higher."],
        merged_context={"coverage": {"ready": True, "total_signals": 4}},
    )
    plan = RoutedContentPlan(
        match_id=6012,
        platform=Platform.WECHAT,
        mode=ContentMode.PRE_MATCH,
        account_id="wechat-main",
        score=100,
        priority=100,
        reason="test",
    )

    titles = [
        "节奏一旦被利物浦拿住，这场就不会好踢",
        "赔率先把门槛摆出来了，切尔西得先跨过去",
        "这场真正难受的，是切尔西要先接住比赛压力",
        "这场先别看热闹，先看利物浦的底层强弱",
    ]
    bodies = [
        "利物浦这场最重要的不是热度，而是能不能把节奏按在自己脚下。\n\n近期走势已经说明，主队更容易把比赛导向自己熟悉的区间。",
        "先别急着谈名气，市场给出来的门槛本身就在表态。\n\n如果赔率、走势和强弱背景同时指向一边，这场就不是一句五五开能带过去的。",
        "这场球最先来的不是技术问题，而是比赛压力。\n\n谁先把情绪和节奏接稳，谁就更像会把方向拿走的那一边。",
        "这场最值得先看的，不是热度，而是底层强弱。\n\n长期强弱差和近期走势叠在一起，主队更像能把比赛拽回自己的轨道。",
    ]
    calls: list[tuple[str, str]] = []

    class FakeLLM:
        def _build_candidate_prompt(self, *, pack, brief, style, outline, angle_spec=None):
            calls.append((style.value, outline.value))
            return type("Prompt", (), {"system_prompt": "s", "user_prompt": "u", "max_tokens": 1800})()

        def generate_json(self, *, system_prompt, user_prompt, max_tokens=None):
            index = len(calls) - 1
            return {"title": titles[index], "content": bodies[index]}

    pipeline.llm = FakeLLM()

    candidate_pool = pipeline._build_candidate_pool(plan, match)

    angle_ids = [item.editorial_metadata.get("wechat_angle_id") for item in candidate_pool]
    openings = [item.content.split("\n\n", 1)[0] for item in candidate_pool]

    assert len(candidate_pool) >= 3
    assert len(set(angle_ids)) == len(angle_ids)
    assert len(set(openings)) == len(openings)


def test_result_flash_candidate_pool_runs_through_editorial_services(tmp_path) -> None:
    settings = Settings(DATABASE_URL=f"sqlite+pysqlite:///{(tmp_path / 'result_flash_engine.db').as_posix()}", RUN_DRY=True)
    pipeline = AutoFootballPipeline(settings)
    match = MatchInfo(
        match_id=6003,
        league="UEFA Champions League",
        match_time=datetime(2026, 5, 6, 19, 0, tzinfo=timezone.utc),
        home_team="Bayern München",
        away_team="Paris Saint Germain",
        home_score=2,
        away_score=1,
        fixture_status="FT",
        fixture_status_text="Finished",
        home_recent_form=["W", "W", "D", "W", "L"],
        away_recent_form=["L", "D", "W", "L", "W"],
        form_summary="Home side held the stronger recent trend before kickoff.",
        knowledge_briefs=["[clubelo] Home side had the stronger long-term profile."],
        merged_context={"coverage": {"ready": True, "total_signals": 4}},
    )
    plan = RoutedContentPlan(
        match_id=6003,
        platform=Platform.WECHAT,
        mode=ContentMode.RESULT_FLASH,
        account_id="wechat-main",
        score=120,
        priority=120,
        reason="test",
    )

    captured: dict[str, object] = {}

    class FakeFactPackService:
        def build(self, content_match, content_plan):
            captured["fact_match_id"] = content_match.match_id
            captured["fact_plan_mode"] = content_plan.mode
            from auto_football.schemas import FactBlockConfidence, FactPack

            return FactPack(
                match_id=content_match.match_id,
                platform=content_plan.platform,
                mode=content_plan.mode,
                readiness=ContentReadiness.HIGH,
                competition_context={"summary": "Semi-final pressure was high."},
                form_signals={"summary": "Home side entered with stronger form."},
                availability_signals={"summary": "No major absences"},
                market_signals={"summary": "Home side was shorter in the market"},
                historical_signals={"summary": "Home side had the stronger recent record"},
                knowledge_signals={"language_goal": "Write for mainstream readers"},
                narrative_hooks=["result widened the pre-match gap"],
                data_gaps=[],
                confidence=FactBlockConfidence(overall=0.91, block_scores={"form_signals": 0.9}),
            )

    class FakeEditorialBriefService:
        def build(self, pack):
            captured["brief_mode"] = pack.mode
            from auto_football.schemas import AudienceLevel, EditorialBrief

            return EditorialBrief(
                platform=pack.platform,
                mode=pack.mode,
                audience_level=AudienceLevel.MAINSTREAM,
                stance=EditorialStance.BALANCED,
                primary_angle="result widened the pre-match gap",
                secondary_angles=["home side justified the market lean"],
                core_claim="The result confirmed the stronger side narrative.",
                supporting_evidence=["Home side entered with stronger form."],
                discussion_hook="",
                prohibited_moves=["Do not overstate certainty."],
                plain_language_guidance=["Keep the recap easy to follow."],
            )

    class FakeStyleRouterService:
        def choose(self, pack, brief, recent_styles=None):
            captured["style_brief_mode"] = brief.mode
            return StyleSelection.MEDIA_COMMENTARY

    class FakeOutlinePlannerService:
        def choose(self, pack, brief, style, recent_pairs=None):
            captured["outline_style"] = style
            return OutlineSelection.RESULT_BACKTRACE

    class FakeValidator:
        def evaluate(self, content, *, pack, brief_stance, recent_openings):
            captured.setdefault("validated_titles", []).append(content.title)
            from auto_football.schemas import CandidateEvaluation

            return CandidateEvaluation(
                plain_language_score=0.93 if content.title == "Flash Winner" else 0.7,
                fact_coverage_score=0.9 if content.title == "Flash Winner" else 0.6,
                platform_fit_score=0.92,
                repetition_penalty=0.0,
                overall_score=0.91 if content.title == "Flash Winner" else 0.67,
                review_summary="ok",
                hard_fail=False,
            )

    class FakeRanker:
        def rank(self, candidates):
            return sorted(candidates, key=lambda item: -item[1].overall_score)

    class FakeLLM:
        def _build_candidate_prompt(self, *, pack, brief, style, outline, angle_spec=None):
            captured["prompt_style"] = style
            captured["prompt_outline"] = outline
            captured.setdefault("angles", []).append(angle_spec)
            return type("Prompt", (), {"system_prompt": "s", "user_prompt": "u", "max_tokens": 1800})()

        def generate_json(self, *, system_prompt, user_prompt, max_tokens=None):
            captured.setdefault("llm_calls", 0)
            captured["llm_calls"] += 1
            if captured["llm_calls"] == 1:
                return {"title": "Flash Winner", "content": "The stronger side finished the job and confirmed the pre-match lean."}
            return {"title": "Flash Backup", "content": "The result still leaves room for discussion around the match flow."}

    pipeline.fact_pack_service = FakeFactPackService()
    pipeline.editorial_brief_service = FakeEditorialBriefService()
    pipeline.style_router_service = FakeStyleRouterService()
    pipeline.outline_planner_service = FakeOutlinePlannerService()
    pipeline.content_validation_service = FakeValidator()
    pipeline.candidate_ranking_service = FakeRanker()
    pipeline.llm = FakeLLM()

    candidate_pool = pipeline._build_candidate_pool(plan, match)

    assert [item.title for item in candidate_pool] == ["Flash Winner", "Flash Backup"]
    assert captured["fact_match_id"] == 6003
    assert captured["fact_plan_mode"] is ContentMode.RESULT_FLASH
    assert captured["brief_mode"] is ContentMode.RESULT_FLASH
    assert captured["style_brief_mode"] is ContentMode.RESULT_FLASH
    assert captured["outline_style"] is StyleSelection.MEDIA_COMMENTARY
    assert captured["prompt_style"] is StyleSelection.MEDIA_COMMENTARY
    assert captured["prompt_outline"] is OutlineSelection.RESULT_BACKTRACE
    assert captured["validated_titles"] == ["Flash Winner", "Flash Backup"]


def test_hot_recap_candidate_pool_runs_through_editorial_services(tmp_path) -> None:
    settings = Settings(DATABASE_URL=f"sqlite+pysqlite:///{(tmp_path / 'hot_recap_engine.db').as_posix()}", RUN_DRY=True)
    pipeline = AutoFootballPipeline(settings)
    match = MatchInfo(
        match_id=6004,
        league="UEFA Champions League",
        match_time=datetime(2026, 5, 6, 19, 0, tzinfo=timezone.utc),
        home_team="Bayern München",
        away_team="Paris Saint Germain",
        home_score=2,
        away_score=1,
        fixture_status="FT",
        fixture_status_text="Finished",
        home_recent_form=["W", "W", "D", "W", "L"],
        away_recent_form=["L", "D", "W", "L", "W"],
        form_summary="Home side carried the stronger longer-term trend into the tie.",
        knowledge_briefs=["[clubelo] Home side had the stronger long-term profile."],
        merged_context={"coverage": {"ready": True, "total_signals": 4}},
    )
    plan = RoutedContentPlan(
        match_id=6004,
        platform=Platform.WECHAT,
        mode=ContentMode.HOT_RECAP,
        account_id="wechat-main",
        score=125,
        priority=125,
        reason="test",
    )

    captured: dict[str, object] = {}

    class FakeFactPackService:
        def build(self, content_match, content_plan):
            captured["fact_match_id"] = content_match.match_id
            captured["fact_plan_mode"] = content_plan.mode
            from auto_football.schemas import FactBlockConfidence, FactPack

            return FactPack(
                match_id=content_match.match_id,
                platform=content_plan.platform,
                mode=content_plan.mode,
                readiness=ContentReadiness.HIGH,
                competition_context={"summary": "Semi-final pressure shaped the tie."},
                form_signals={"summary": "Home side had the stronger trend before kickoff."},
                availability_signals={"summary": "No major absences"},
                market_signals={"summary": "Home side was shorter in the market"},
                historical_signals={"summary": "The result reinforced the bigger pattern."},
                knowledge_signals={"language_goal": "Write for mainstream readers"},
                narrative_hooks=["the result confirms the wider story"],
                data_gaps=[],
                confidence=FactBlockConfidence(overall=0.92, block_scores={"form_signals": 0.9}),
            )

    class FakeEditorialBriefService:
        def build(self, pack):
            captured["brief_mode"] = pack.mode
            from auto_football.schemas import AudienceLevel, EditorialBrief

            return EditorialBrief(
                platform=pack.platform,
                mode=pack.mode,
                audience_level=AudienceLevel.MAINSTREAM,
                stance=EditorialStance.BALANCED,
                primary_angle="the result confirms the wider story",
                secondary_angles=["home side justified the market lean"],
                core_claim="The bigger narrative held up under match pressure.",
                supporting_evidence=["Home side had the stronger trend before kickoff."],
                discussion_hook="",
                prohibited_moves=["Do not overstate certainty."],
                plain_language_guidance=["Keep the recap easy to follow."],
            )

    class FakeStyleRouterService:
        def choose(self, pack, brief, recent_styles=None):
            captured["style_brief_mode"] = brief.mode
            return StyleSelection.MEDIA_COMMENTARY

    class FakeOutlinePlannerService:
        def choose(self, pack, brief, style, recent_pairs=None):
            captured["outline_style"] = style
            return OutlineSelection.TREND_BREAKDOWN

    class FakeValidator:
        def evaluate(self, content, *, pack, brief_stance, recent_openings):
            captured.setdefault("validated_titles", []).append(content.title)
            from auto_football.schemas import CandidateEvaluation

            return CandidateEvaluation(
                plain_language_score=0.94 if content.title == "Recap Winner" else 0.72,
                fact_coverage_score=0.9 if content.title == "Recap Winner" else 0.61,
                platform_fit_score=0.91,
                repetition_penalty=0.0,
                overall_score=0.92 if content.title == "Recap Winner" else 0.69,
                review_summary="ok",
                hard_fail=False,
            )

    class FakeRanker:
        def rank(self, candidates):
            return sorted(candidates, key=lambda item: -item[1].overall_score)

    class FakeLLM:
        def _build_candidate_prompt(self, *, pack, brief, style, outline, angle_spec=None):
            captured["prompt_style"] = style
            captured["prompt_outline"] = outline
            captured.setdefault("angles", []).append(angle_spec)
            return type("Prompt", (), {"system_prompt": "s", "user_prompt": "u", "max_tokens": 1800})()

        def generate_json(self, *, system_prompt, user_prompt, max_tokens=None):
            captured.setdefault("llm_calls", 0)
            captured["llm_calls"] += 1
            if captured["llm_calls"] == 1:
                return {"title": "Recap Winner", "content": "The final score ended up reinforcing the bigger story around the tie."}
            return {"title": "Recap Backup", "content": "The wider trend still matters even if the scoreline was tight."}

    pipeline.fact_pack_service = FakeFactPackService()
    pipeline.editorial_brief_service = FakeEditorialBriefService()
    pipeline.style_router_service = FakeStyleRouterService()
    pipeline.outline_planner_service = FakeOutlinePlannerService()
    pipeline.content_validation_service = FakeValidator()
    pipeline.candidate_ranking_service = FakeRanker()
    pipeline.llm = FakeLLM()

    candidate_pool = pipeline._build_candidate_pool(plan, match)

    assert [item.title for item in candidate_pool] == ["Recap Winner", "Recap Backup"]
    assert captured["fact_match_id"] == 6004
    assert captured["fact_plan_mode"] is ContentMode.HOT_RECAP
    assert captured["brief_mode"] is ContentMode.HOT_RECAP
    assert captured["style_brief_mode"] is ContentMode.HOT_RECAP
    assert captured["outline_style"] is StyleSelection.MEDIA_COMMENTARY
    assert captured["prompt_style"] is StyleSelection.MEDIA_COMMENTARY
    assert captured["prompt_outline"] is OutlineSelection.TREND_BREAKDOWN
    assert captured["validated_titles"] == ["Recap Winner", "Recap Backup"]
