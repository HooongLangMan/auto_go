from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from langgraph.graph import END, START, StateGraph

from auto_football.adapters import PublisherRegistry
from auto_football.cache import CacheStore
from auto_football.clients import (
    ApiFootballClient,
    ChatCompletionClient,
    ClubEloClient,
    FBrefClient,
    FootballDataClient,
    OpenFootballClient,
    PublicMatchClient,
    SofascoreClient,
    StatsBombOpenClient,
    TheSportsDBClient,
    WhoScoredClient,
)
from auto_football.config import Settings
from auto_football.db import Database
from auto_football.images import MatchImageGenerator
from auto_football.knowledge import MultiSourceKnowledgeService
from auto_football.routing import ContentRouter
from auto_football.schemas import ContentMode, ContentStatus, GeneratedContent, MatchInfo, MergedMatchContext, Platform, RoutedContentPlan, SelectionDecision, StyleSelection
from auto_football.state import GraphState
from auto_football.structured_data import StructuredDataService
from auto_football.domain.services.content_generation_service import ContentGenerationService
from auto_football.domain.services.fact_pack_service import FactPackService
from auto_football.domain.services.editorial_brief_service import EditorialBriefService
from auto_football.domain.services.style_router_service import StyleRouterService
from auto_football.domain.services.outline_planner_service import OutlinePlannerService
from auto_football.domain.services.content_validation_service import ContentValidationService
from auto_football.domain.services.candidate_ranking_service import CandidateRankingService
from auto_football.domain.services.fixture_selection_service import FixtureSelectionService
from auto_football.domain.services.image_generation_service import ImageGenerationService
from auto_football.domain.services.distribution_service import DistributionService
from auto_football.domain.services.match_enrichment_service import MatchEnrichmentService
from auto_football.domain.services.wechat_angle_planner_service import WechatAnglePlannerService
from auto_football.domain.services.visual_brief_service import VisualBriefService
from auto_football.infra.images.ark_image_client import ArkImageClient


REQUIRED_SLOTS = [
    "home_team",
    "away_team",
    "match_time",
    "home_recent_form",
    "away_recent_form",
]

LEAGUE_PRIORITY = {
    "UEFA Champions League": 100,
    "Premier League": 95,
    "La Liga": 90,
    "Serie A": 88,
    "Bundesliga": 87,
    "Ligue 1": 85,
    "UEFA Europa League": 82,
    "Chinese Super League": 70,
    "CSL": 70,
}

PRIORITY_LEAGUES = {
    "Premier League",
    "La Liga",
    "Serie A",
    "Bundesliga",
    "Ligue 1",
}

ELITE_CLUB_ALIASES = {
    "Arsenal",
    "Chelsea",
    "Liverpool",
    "Manchester City",
    "Man City",
    "Manchester United",
    "Man United",
    "Tottenham",
    "Newcastle",
    "Bayern Munich",
    "Bayern",
    "Borussia Dortmund",
    "Dortmund",
    "Bayer Leverkusen",
    "Leverkusen",
    "RB Leipzig",
    "Leipzig",
    "Real Madrid",
    "Barcelona",
    "Atletico Madrid",
    "Atletico",
    "Sevilla",
    "Inter",
    "Inter Milan",
    "AC Milan",
    "Milan",
    "Juventus",
    "Napoli",
    "Roma",
    "Lazio",
    "Atalanta",
    "Paris Saint Germain",
    "Paris SG",
    "PSG",
    "Marseille",
    "Monaco",
    "Lyon",
    "Lille",
    "Nice",
    "Benfica",
    "Porto",
    "Sporting CP",
    "Sporting",
    "Ajax",
    "PSV",
    "Feyenoord",
    "Celtic",
    "Rangers",
    "Galatasaray",
    "Fenerbahce",
    "Besiktas",
    "Club Brugge",
    "Anderlecht",
    "Red Bull Salzburg",
    "Salzburg",
    "Dinamo Zagreb",
    "Shakhtar Donetsk",
    "Shakhtar",
    "Dynamo Kyiv",
    "Olympiacos",
    "Panathinaikos",
    "AEK Athens",
    "Sparta Prague",
    "Slavia Prague",
    "Red Star Belgrade",
    "Young Boys",
    "Basel",
    "FC Copenhagen",
    "Copenhagen",
    "Midtjylland",
    "Bodo/Glimt",
}

WECHAT_MIN_LENGTH = 800
WECHAT_MAX_LENGTH = 1500
XHS_MIN_LENGTH = 200
XHS_MAX_LENGTH = 500


class AutoFootballPipeline:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.db = Database(settings)
        self.db.init_db()
        self.cache = CacheStore(settings)
        self.api_football = ApiFootballClient(settings)
        self.public_match = PublicMatchClient(settings)
        self.the_sports_db = TheSportsDBClient(settings)
        self.clubelo = ClubEloClient(settings)
        self.football_data = FootballDataClient(settings)
        self.sofascore = SofascoreClient(settings)
        self.openfootball = OpenFootballClient(settings)
        self.statsbomb = StatsBombOpenClient(settings)
        self.fbref = FBrefClient(settings)
        self.whoscored = WhoScoredClient(settings)
        self.knowledge = MultiSourceKnowledgeService(self.cache, self.db, self.clubelo, self.openfootball, self.statsbomb, self.fbref, self.whoscored)
        self.structured_data = StructuredDataService(self.football_data, self.sofascore, self.openfootball, self.clubelo)
        self.llm = ChatCompletionClient(settings)
        self.router = ContentRouter(settings)
        self.publisher = PublisherRegistry(settings)
        self.image_generator = MatchImageGenerator(settings)
        self.selection_service = FixtureSelectionService(self.router, self.db, self._reference_time)
        self.enrichment_service = MatchEnrichmentService(
            db=self.db,
            api_football=self.api_football,
            structured_data=self.structured_data,
            knowledge=self.knowledge,
            the_sports_db=self.the_sports_db,
            run_date_getter=lambda: self.run_date,
            build_match_from_public=self._build_match_from_public,
            public_key_fn=self._public_key,
            public_odds_fn=self._public_odds,
            public_status_code_fn=self._public_status_code,
            has_required_slots_fn=self._has_required_slots,
        )
        self.fact_pack_service = FactPackService()
        self.editorial_brief_service = EditorialBriefService()
        self.style_router_service = StyleRouterService()
        self.outline_planner_service = OutlinePlannerService()
        self.wechat_angle_planner_service = WechatAnglePlannerService()
        self.content_validation_service = ContentValidationService()
        self.candidate_ranking_service = CandidateRankingService()
        self.content_service = ContentGenerationService(self.db, self._build_candidate_pool)
        self.visual_brief_service = VisualBriefService()
        self.ai_image_client = ArkImageClient(settings)
        self.image_service = ImageGenerationService(
            self.db,
            self.image_generator,
            self._verdict,
            self._image_prompts_for_mode,
            visual_brief_service=self.visual_brief_service,
            ai_image_client=self.ai_image_client,
            settings=settings,
        )
        self.distribution_service = DistributionService(settings, self.publisher, self.db)
        self.run_date = date.today()
        self.public_daily_matches: list[dict[str, Any]] = []
        self.api_daily_matches: list[dict[str, Any]] = []
        self.recent_styles_by_platform: dict[str, list[StyleSelection]] = {}
        self.recent_pairs_by_platform: dict[str, list[tuple[StyleSelection, OutlineSelection]]] = {}
        self.recent_openings_by_platform: dict[str, list[str]] = {}

    def build(self):
        graph = StateGraph(GraphState)
        graph.add_node("crawler", self.crawler)
        graph.add_node("selector", self.selector)
        graph.add_node("enrichment", self.enrichment)
        graph.add_node("content", self.content_generation)
        graph.add_node("image", self.image_generation)
        graph.add_node("distribution", self.distribution)

        graph.add_edge(START, "crawler")
        graph.add_edge("crawler", "selector")
        graph.add_edge("selector", "enrichment")
        graph.add_edge("enrichment", "content")
        graph.add_edge("content", "image")
        graph.add_edge("image", "distribution")
        graph.add_edge("distribution", END)
        return graph.compile()

    def run(self, *, run_date: date) -> GraphState:
        self.run_date = run_date
        graph = self.build()
        initial_state: GraphState = {
            "run_id": 0,
            "fixtures": [],
            "selected_match_ids": [],
            "selection_results": [],
            "content_plans": [],
            "match_data": {},
            "merged_contexts": {},
            "contents": [],
            "publish_status": {},
        }
        final_state = graph.invoke(initial_state)
        self.db.complete_run(
            final_state["run_id"],
            selected_match_ids=final_state["selected_match_ids"],
            source_summary={
                "api_football_fixtures": len(self.api_daily_matches),
                "public_fixtures": len(self.public_daily_matches),
                "merged_contexts": len(final_state["merged_contexts"]),
            },
        )
        return final_state

    def crawler(self, state: GraphState) -> dict[str, Any]:
        run_id = self.db.create_run(self.run_date)
        window_dates = [date.fromordinal(self.run_date.toordinal() + offset) for offset in (-1, 0, 1)]

        self.api_daily_matches = self._collect_fixture_window(run_id, "api_football", window_dates)
        self.public_daily_matches = self._collect_fixture_window(run_id, "public", window_dates)

        fixtures = self._dedupe_fixtures([*self.api_daily_matches, *self.public_daily_matches])
        return {"run_id": run_id, "fixtures": fixtures}

    def selector(self, state: GraphState) -> dict[str, Any]:
        selected, decisions, plans = self.selection_service.select(run_id=state["run_id"], fixtures=state["fixtures"])
        return {"selected_match_ids": selected, "selection_results": decisions, "content_plans": plans}

    def enrichment(self, state: GraphState) -> dict[str, Any]:
        results, merged_contexts = self.enrichment_service.enrich(
            run_id=state["run_id"],
            selected_match_ids=state["selected_match_ids"],
            public_daily_matches=self.public_daily_matches,
        )
        return {"match_data": results, "merged_contexts": merged_contexts}

    def content_generation(self, state: GraphState) -> dict[str, Any]:
        return {"contents": self.content_service.generate(state["content_plans"], state["match_data"])}

    def image_generation(self, state: GraphState) -> dict[str, Any]:
        return {"contents": self.image_service.generate(state["contents"], state["match_data"])}

    def distribution(self, state: GraphState) -> dict[str, Any]:
        return {"publish_status": self.distribution_service.distribute(state["contents"], state["match_data"])}

    @staticmethod
    def _fixture_id(fixture: dict[str, Any]) -> int | None:
        if "fixture" in fixture:
            return fixture.get("fixture", {}).get("id")
        return fixture.get("id")

    @staticmethod
    def _fixture_league_name(fixture: dict[str, Any]) -> str:
        if "league" in fixture:
            return fixture.get("league", {}).get("name", "")
        return fixture.get("competition_name_en", "")

    @staticmethod
    def _fixture_time_value(fixture: dict[str, Any]) -> str:
        if "fixture" in fixture:
            return fixture.get("fixture", {}).get("date", "")
        return str(fixture.get("time", ""))

    @staticmethod
    def _fixture_home_team_name(fixture: dict[str, Any]) -> str:
        if "teams" in fixture:
            return fixture.get("teams", {}).get("home", {}).get("name", "")
        return fixture.get("home_team_name_en") or fixture.get("home_team_name_zh") or ""

    @staticmethod
    def _fixture_away_team_name(fixture: dict[str, Any]) -> str:
        if "teams" in fixture:
            return fixture.get("teams", {}).get("away", {}).get("name", "")
        return fixture.get("away_team_name_en") or fixture.get("away_team_name_zh") or ""

    @staticmethod
    def _normalize_club_name(name: str | None) -> str:
        if not name:
            return ""
        return "".join(ch for ch in name.lower() if ch.isalnum())

    @classmethod
    def _is_elite_fixture(cls, home_team: str, away_team: str) -> bool:
        elite = {cls._normalize_club_name(item) for item in ELITE_CLUB_ALIASES}
        return cls._normalize_club_name(home_team) in elite or cls._normalize_club_name(away_team) in elite

    @staticmethod
    def _public_key(home: str | None, away: str | None) -> str:
        return f"{AutoFootballPipeline._normalize_name(home)}::{AutoFootballPipeline._normalize_name(away)}"

    @staticmethod
    def _normalize_name(name: str | None) -> str:
        if not name:
            return ""
        return "".join(ch for ch in name.lower() if ch.isalnum())

    @staticmethod
    def _public_odds(item: dict[str, Any] | None) -> dict[str, Any] | None:
        if not item:
            return None
        value = item.get("exponent")
        return value if isinstance(value, dict) else None

    @staticmethod
    def _public_status_code(item: dict[str, Any] | None) -> str | None:
        if not item:
            return None
        status = item.get("status")
        return str(status) if status is not None else None

    def _build_match_from_public(self, item: dict[str, Any]) -> MatchInfo:
        home_team = item.get("home_team_name_en") or item.get("home_team_name_zh") or "Unknown"
        away_team = item.get("away_team_name_en") or item.get("away_team_name_zh") or "Unknown"
        home_artwork = self.the_sports_db.get_team_artwork(home_team)
        away_artwork = self.the_sports_db.get_team_artwork(away_team)
        timestamp = int(item.get("time") or 0)
        match_time = datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp else datetime.combine(self.run_date, datetime.min.time(), tzinfo=timezone.utc)
        return MatchInfo(
            match_id=int(item["id"]),
            league=item.get("competition_name_en") or item.get("competition_name_zh") or "Unknown",
            match_time=match_time,
            home_team=home_team,
            away_team=away_team,
            home_recent_form=[],
            away_recent_form=[],
            injuries=None,
            odds=self._public_odds(item),
            home_logo_url=item.get("home_team_log") or home_artwork.get("badge") or home_artwork.get("logo"),
            away_logo_url=item.get("away_team_log") or away_artwork.get("badge") or away_artwork.get("logo"),
            competition_logo_url=item.get("competition_logo"),
            theme_color=item.get("primary_color"),
            fixture_status=self._public_status_code(item),
            fixture_status_text=item.get("status_str") or "状态待确认",
            home_score=self._safe_int(item.get("home_score")),
            away_score=self._safe_int(item.get("away_score")),
            must_fill=False,
        )

    def _build_content_for_plan(self, plan: RoutedContentPlan, match: MatchInfo) -> GeneratedContent:
        if plan.platform is Platform.WECHAT:
            if plan.mode is ContentMode.RESULT_FLASH:
                content = self._fallback_wechat_result(match)
            elif plan.mode is ContentMode.HOT_RECAP:
                content = self._fallback_wechat_hot_recap(match)
            else:
                content = self._build_wechat_content(match)
            max_length = WECHAT_MAX_LENGTH
        else:
            if plan.mode is ContentMode.RESULT_FLASH:
                content = self._fallback_xhs_result(match)
            elif plan.mode is ContentMode.HOT_RECAP:
                content = self._fallback_xhs_hot_recap(match)
            else:
                content = self._build_xhs_content(match)
            max_length = XHS_MAX_LENGTH

        content.match_id = match.match_id
        content.mode = plan.mode
        content.account_id = plan.account_id
        content.status = ContentStatus.READY_TO_PUBLISH
        content.priority = plan.priority
        content.tags = content.tags or self._default_tags_for_plan(plan, match)
        content.title = self._sanitize_title(content.title)
        content.content = self._truncate_content(self._normalize_content(content.content), max_length)
        return content

    def _build_candidate_pool(self, plan: RoutedContentPlan, match: MatchInfo) -> list[GeneratedContent]:
        if plan.mode not in {ContentMode.PRE_MATCH, ContentMode.RESULT_FLASH, ContentMode.HOT_RECAP}:
            return [self._build_content_for_plan(plan, match)]

        coverage = (match.merged_context or {}).get("coverage") or {}
        if coverage.get("ready") is False:
            if not self._lightweight_content_allowed(plan, coverage):
                return []
        elif coverage.get("ready") is None:
            return []

        platform_key = plan.platform.value
        recent_styles = list(self.recent_styles_by_platform.get(platform_key, []))
        recent_pairs = list(self.recent_pairs_by_platform.get(platform_key, []))
        recent_openings = list(self.recent_openings_by_platform.get(platform_key, []))

        pack = self.fact_pack_service.build(match, plan)
        brief = self.editorial_brief_service.build(pack)

        drafted_candidates: list[tuple[GeneratedContent, Any, StyleSelection, OutlineSelection]] = []
        local_recent_styles = list(recent_styles)
        local_recent_pairs = list(recent_pairs)
        angle_specs = []
        if plan.platform is Platform.WECHAT and plan.mode is ContentMode.PRE_MATCH:
            angle_specs = self.wechat_angle_planner_service.build(pack, brief)
        candidate_target_count = self._candidate_target_count(plan, angle_specs=angle_specs)

        for index in range(candidate_target_count):
            style = self.style_router_service.choose(pack, brief, recent_styles=local_recent_styles)
            outline = self.outline_planner_service.choose(pack, brief, style, recent_pairs=local_recent_pairs)
            angle_spec = angle_specs[index] if index < len(angle_specs) else None
            prompt = self.llm._build_candidate_prompt(
                pack=pack,
                brief=brief,
                style=style,
                outline=outline,
                angle_spec=angle_spec,
            )
            payload = self.llm.generate_json(
                system_prompt=prompt.system_prompt,
                user_prompt=prompt.user_prompt,
                max_tokens=prompt.max_tokens,
            )
            candidate = self._candidate_from_payload(plan, match, pack, brief, style, outline, payload, angle_spec=angle_spec)
            if plan.platform is Platform.WECHAT:
                candidate.content = self._expand_wechat_longform(candidate.content, match, angle_spec=angle_spec)
            evaluation = self.content_validation_service.evaluate(
                candidate,
                pack=pack,
                brief_stance=brief.stance,
                recent_openings=recent_openings,
            )
            drafted_candidates.append((candidate, evaluation, style, outline))
            local_recent_styles.append(style)
            local_recent_pairs.append((style, outline))

        if not drafted_candidates:
            return [self._build_content_for_plan(plan, match)]

        ranked_pairs = self.candidate_ranking_service.rank(
            [(candidate, evaluation) for candidate, evaluation, _, _ in drafted_candidates]
        )
        evaluation_lookup = {id(candidate): evaluation for candidate, evaluation, _, _ in drafted_candidates}
        style_lookup = {id(candidate): style for candidate, _, style, _ in drafted_candidates}
        outline_lookup = {id(candidate): outline for candidate, _, _, outline in drafted_candidates}

        ranked_candidates: list[GeneratedContent] = []
        for candidate, evaluation in ranked_pairs:
            existing_metadata = dict(candidate.editorial_metadata or {})
            candidate.editorial_style = style_lookup[id(candidate)]
            candidate.editorial_outline = outline_lookup[id(candidate)]
            candidate.content_readiness = pack.readiness
            candidate.quality_summary = evaluation.review_summary
            candidate.editorial_metadata = {
                **existing_metadata,
                "fact_pack": pack.model_dump(mode="json"),
                "brief": brief.model_dump(mode="json"),
                "evaluation": evaluation.model_dump(mode="json"),
            }
            ranked_candidates.append(candidate)

        top_candidate = ranked_candidates[0]
        self.recent_styles_by_platform.setdefault(platform_key, []).append(top_candidate.editorial_style)
        self.recent_pairs_by_platform.setdefault(platform_key, []).append(
            (top_candidate.editorial_style, top_candidate.editorial_outline)
        )
        opening = ContentValidationService.opening_line(top_candidate.content)
        if opening:
            self.recent_openings_by_platform.setdefault(platform_key, []).append(opening)
        return ranked_candidates

    @staticmethod
    def _lightweight_content_allowed(plan: RoutedContentPlan, coverage: dict[str, Any]) -> bool:
        if plan.platform is not Platform.XIAOHONGSHU:
            return False
        if plan.mode is not ContentMode.PRE_MATCH:
            return False
        total_signals = int(coverage.get("total_signals") or 0)
        return total_signals >= 2

    def _candidate_target_count(self, plan: RoutedContentPlan, *, angle_specs: list[Any] | None = None) -> int:
        if plan.platform is Platform.WECHAT and plan.mode is ContentMode.PRE_MATCH and angle_specs:
            return len(angle_specs)
        if plan.platform is Platform.XIAOHONGSHU:
            return 2
        return 2

    def _candidate_from_payload(
        self,
        plan: RoutedContentPlan,
        match: MatchInfo,
        pack,
        brief,
        style: StyleSelection,
        outline: OutlineSelection,
        payload: dict[str, Any] | None,
        *,
        angle_spec=None,
    ) -> GeneratedContent:
        max_length = WECHAT_MAX_LENGTH if plan.platform is Platform.WECHAT else XHS_MAX_LENGTH
        title = ""
        content = ""
        if payload:
            title = str(payload.get("title") or "")
            content = str(payload.get("content") or "")

        if not title.strip() or not content.strip():
            if plan.platform is Platform.WECHAT and plan.mode is ContentMode.PRE_MATCH:
                fallback = self._fallback_wechat_variant(match, style=style, outline=outline, angle_spec=angle_spec)
            else:
                fallback = self._build_content_for_plan(plan, match)
            title = fallback.title
            content = fallback.content

        content = self._apply_section_rules_to_generated_content(plan, match, content)
        if plan.platform is Platform.WECHAT:
            content = self._expand_wechat_longform(content, match, angle_spec=angle_spec)
        metadata = {
            "fact_pack": pack.model_dump(mode="json"),
            "brief": brief.model_dump(mode="json"),
        }
        if angle_spec is not None:
            angle_payload = angle_spec.model_dump(mode="json") if hasattr(angle_spec, "model_dump") else dict(angle_spec)
            metadata["wechat_angle_id"] = angle_payload.get("angle_id")
            metadata["wechat_angle"] = angle_payload

        return GeneratedContent(
            match_id=match.match_id,
            platform=plan.platform,
            mode=plan.mode,
            account_id=plan.account_id,
            priority=plan.priority,
            title=self._sanitize_title(title),
            content=self._truncate_content(self._normalize_content(content), max_length),
            tags=self._default_tags_for_plan(plan, match),
            editorial_style=style,
            editorial_outline=outline,
            content_readiness=pack.readiness,
            editorial_metadata=metadata,
        )

    def _collect_fixture_window(self, run_id: int, source: str, window_dates: list[date]) -> list[dict[str, Any]]:
        if source == "api_football" and not self.api_football.enabled:
            return []
        fixtures: list[dict[str, Any]] = []
        for target_date in window_dates:
            cache_key = self.cache.fixture_list_key(target_date, source)
            payload = self.cache.get_json(cache_key)
            if payload is None:
                payload = self.api_football.get_daily_fixtures(target_date) if source == "api_football" else self.public_match.get_daily_matches(target_date)
            if not payload:
                continue
            payload = self._filter_source_fixtures(source, payload)
            if not payload:
                continue
            self.cache.set_json(cache_key, payload, ttl_seconds=self.settings.fixture_cache_ttl_seconds)
            self.db.save_raw_fixtures(run_id, target_date, source, payload)
            fixtures.extend(payload)
        return fixtures

    def _reference_time(self) -> datetime:
        current_utc = datetime.now(timezone.utc)
        if self.run_date == current_utc.date():
            return current_utc
        return datetime.combine(self.run_date, datetime.min.time(), tzinfo=timezone.utc).replace(hour=12)

    @staticmethod
    def _dedupe_fixtures(fixtures: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: dict[int, dict[str, Any]] = {}
        for fixture in fixtures:
            fixture_id = AutoFootballPipeline._fixture_id(fixture)
            if fixture_id is None:
                continue
            deduped[fixture_id] = fixture
        return list(deduped.values())

    @staticmethod
    def _filter_source_fixtures(source: str, fixtures: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if source != "public":
            return fixtures
        filtered: list[dict[str, Any]] = []
        for fixture in fixtures:
            match_type = str(fixture.get("match_type") or "").lower()
            if match_type and match_type != "football":
                continue
            filtered.append(fixture)
        return filtered

    @staticmethod
    def _image_prompts_for_mode(match: MatchInfo, mode: ContentMode, verdict: str) -> list[str]:
        if mode is ContentMode.RESULT_FLASH:
            return [
                f"{match.home_team} vs {match.away_team} match result poster, final score {match.home_score}-{match.away_score}",
                f"{match.home_team} vs {match.away_team} stadium action recap, {match.league}",
            ]
        if mode is ContentMode.HOT_RECAP:
            return [
                f"{match.home_team} vs {match.away_team} hot recap editorial cover, {match.league}",
                f"{match.home_team} and {match.away_team} premium football story card, dramatic action",
            ]
        return [
            f"{match.home_team} vs {match.away_team} premium football poster, {match.league}",
            f"{match.home_team} vs {match.away_team} score prediction board, {verdict}",
        ]

    @staticmethod
    def _default_tags_for_plan(plan: RoutedContentPlan, match: MatchInfo) -> list[str]:
        mode_tag_map = {
            ContentMode.PRE_MATCH: "赛前分析",
            ContentMode.RESULT_FLASH: "赛果快评",
            ContentMode.HOT_RECAP: "热点复盘",
        }
        tags = [
            "足球",
            mode_tag_map.get(plan.mode, plan.mode.value),
            match.league,
            match.home_team,
            match.away_team,
        ]
        deduped: list[str] = []
        for tag in tags:
            cleaned = str(tag).strip()
            if cleaned and cleaned not in deduped:
                deduped.append(cleaned)
        return deduped[:8]

    def _build_wechat_content(self, match: MatchInfo) -> GeneratedContent:
        generated = self.llm.generate_platform_content(match, Platform.WECHAT)
        if generated:
            generated.title = self._sanitize_title(generated.title)
            generated.content = self._truncate_content(self._normalize_content(generated.content), WECHAT_MAX_LENGTH)
            if self._length_ok(generated.content, WECHAT_MIN_LENGTH, WECHAT_MAX_LENGTH):
                return generated
        fallback = self._fallback_wechat(match)
        fallback.title = self._sanitize_title(fallback.title)
        fallback.content = self._truncate_content(self._normalize_content(fallback.content), WECHAT_MAX_LENGTH)
        return fallback

    def _build_xhs_content(self, match: MatchInfo) -> GeneratedContent:
        generated = self.llm.generate_platform_content(match, Platform.XIAOHONGSHU)
        if generated:
            generated.title = self._sanitize_title(generated.title)
            generated.content = self._truncate_content(self._normalize_content(generated.content), XHS_MAX_LENGTH)
            if self._length_ok(generated.content, XHS_MIN_LENGTH, XHS_MAX_LENGTH):
                return generated
        fallback = self._fallback_xhs(match)
        fallback.title = self._sanitize_title(fallback.title)
        fallback.content = self._truncate_content(self._normalize_content(fallback.content), XHS_MAX_LENGTH)
        return fallback

    @staticmethod
    def _has_required_slots(payload: dict[str, Any]) -> bool:
        return all(bool(payload.get(name)) for name in REQUIRED_SLOTS)

    @staticmethod
    def _fallback_wechat(match: MatchInfo) -> GeneratedContent:
        verdict = AutoFootballPipeline._verdict(match)
        section_rules = AutoFootballPipeline._section_rules_for_match(match)
        rank_sentence = (
            f"{match.standings_summary}"
            if match.standings_summary
            else
            f"从排名来看，主队目前在联赛中排第{match.home_rank}位，客队排第{match.away_rank}位，"
            if match.home_rank and match.away_rank
            else "从排名维度看，两队当前公开的名次信息并不完整，所以更要回到比赛内容和近期表现本身。"
        )
        form_sentence = (
            f"{match.form_summary}"
            if match.form_summary
            else
            f"主队最近五场打出{'、'.join(match.home_recent_form) or '待补充'}，"
            f"客队最近五场则是{'、'.join(match.away_recent_form) or '待补充'}。"
        )
        injuries = "；".join(match.injuries[:4]) if match.injuries else "目前没有足够明确的关键伤停名单"
        odds_text = AutoFootballPipeline._format_odds_text(match.odds)
        knowledge_text = "；".join(match.knowledge_briefs[:4]) if match.knowledge_briefs else "暂无额外外部知识补充"
        paragraphs = [
            (
                f"{match.home_team}对阵{match.away_team}这场比赛，我的判断先摆在前面：目前更倾向于{verdict}。"
                "对公众号读者来说，赛前分析最重要的不是绕很多弯，而是先把方向说清楚，再解释这个判断的底层依据。"
                "只要结论足够明确，后面的数据和推演才有意义。"
            )
        ]
        if section_rules.get("background") != "skip":
            paragraphs.append(
                (
                    f"{rank_sentence}"
                    "排名高的一方通常意味着赛季稳定性更强，尤其在联赛进入中后段后，名次往往能反映球队执行力、抗波动能力和阵容厚度。"
                    "当然，名次不是唯一答案，但它依然是很有参考价值的一层底盘。"
                )
            )
        if section_rules.get("form") != "skip":
            paragraphs.append(
                (
                    f"{form_sentence}"
                    "近五场走势虽然样本不算特别大，但足够帮助我们判断球队现在到底是在上升、横盘，还是已经进入明显回落阶段。"
                    "如果一支球队连续拿分，说明它的比赛内容和临场处理大概率更稳；反过来，走势起伏大的球队，到了关键回合更容易掉线。"
                )
            )
        if section_rules.get("availability") != "skip":
            paragraphs.append(
                (
                    f"伤停层面同样重要，{injuries}。"
                    "尤其是涉及中卫、后腰、核心前锋或者边路推进点的时候，影响绝不只是少一个名字那么简单，"
                    "而是会直接改变球队的推进速度、压迫强度以及禁区内的终结质量。"
                )
            )
        if section_rules.get("market") != "skip":
            paragraphs.append(
                (
                    f"赔率和市场倾向这边，目前能参考到的摘要是：{odds_text}。"
                    "赔率本身不是比分，但它会反映市场对强弱关系的基础预期。"
                    "如果纸面实力、近期状态和赔率方向一致，那么赛前判断一般会更顺；如果三者出现明显冲突，临场就必须提高警惕。"
                )
            )
        paragraphs.extend(
            [
                (
                    f"另外，多源补充信息给出的背景是：{knowledge_text}。"
                    "这类外部知识不会直接替代赛前事实，但能帮助我们理解球队的长期强弱、风格和历史轨迹，"
                    "让最终判断不至于只依赖单一数据源。"
                ),
                (
                    f"综合这些信息，我依旧维持{verdict}这个方向。"
                    "这不代表比赛一定会打成一边倒，而是说从赛前视角看，哪一边更值得优先支持已经比较清楚。"
                    "只要临场首发没有突然出现重大变化，这个判断大概率不会轻易反转。"
                ),
            ]
        )
        fillers = [
            "还有一个容易被忽视的因素，是比赛时段和赛程密度。密集赛程下，球队在下半场的回追速度、对抗质量和定位球保护，往往会出现肉眼可见的差异，这也是很多比赛后程突然转向的原因。",
            "所以这场更适合用“方向判断”去看，而不是把话说得太满。内容只要抓住关键信息和清晰观点，反而更适合公众号阅读节奏，也更容易提高读者留存。",
        ]
        content = "\n\n".join(paragraphs)
        for filler in fillers:
            if len(content) >= WECHAT_MIN_LENGTH:
                break
            content = f"{content}\n\n{filler}"
        return GeneratedContent(
            platform=Platform.WECHAT,
            title=f"{match.home_team}vs{match.away_team}：这场不用铺垫，先给你一个清晰方向",
            content=AutoFootballPipeline._truncate_content(content, WECHAT_MAX_LENGTH),
        )

    @staticmethod
    def _fallback_wechat_variant(
        match: MatchInfo,
        *,
        style: StyleSelection,
        outline: OutlineSelection,
        angle_spec=None,
    ) -> GeneratedContent:
        del outline
        verdict = AutoFootballPipeline._verdict(match)
        form_text = f"{match.home_team}近况 {'/'.join(match.home_recent_form) or '待补充'}，{match.away_team}近况 {'/'.join(match.away_recent_form) or '待补充'}。"
        odds_text = AutoFootballPipeline._format_odds_text(match.odds)
        knowledge_text = "；".join(match.knowledge_briefs[:3]) if match.knowledge_briefs else "外部背景补充有限。"
        angle_payload = angle_spec.model_dump(mode="json") if hasattr(angle_spec, "model_dump") else dict(angle_spec or {})
        angle_id = str(angle_payload.get("angle_id") or "")

        if angle_id == "market_tension":
            content = "\n\n".join(
                [
                    f"先别急着把这场写成普通强弱对话，市场给出来的第一道门槛已经说明，{verdict}这个方向不是空口判断。",
                    f"{odds_text} 这些数字不会替你拍板，但它们会把比赛预期先摆上桌面。",
                    f"{form_text} 当走势、赔率和临场承压能力开始往同一边收束时，这场就很难再用一句五五开带过去。",
                    f"{knowledge_text} 把这些信号并起来看，{verdict}更像是顺着比赛纹理读出来的方向。",
                ]
            )
            title = f"{match.home_team}vs{match.away_team}：盘口先亮态度，比赛才开始说话"
            return GeneratedContent(platform=Platform.WECHAT, title=title, content=content)

        if angle_id == "pressure_line":
            content = "\n\n".join(
                [
                    f"这场球最先来到台前的，不是技巧细节，而是谁更能把比赛压力接稳。就这点看，{verdict}依然更顺。",
                    f"{form_text} 近期走势之所以重要，不只是输赢记录，而是谁更像能在比赛变紧的时候保持节奏完整。",
                    f"{odds_text} 真到比赛进入拉扯段，承压能力往往比纸面名气更值钱，市场也侧面把这种预期抬了出来。",
                    f"{knowledge_text} 如果比赛情绪被放大，方向大概率不会脱离这条压力线。",
                ]
            )
            title = f"{match.home_team}vs{match.away_team}：真正难的不是开场，而是谁先扛住压力"
            return GeneratedContent(platform=Platform.WECHAT, title=title, content=content)

        if angle_id == "strength_snapshot":
            content = "\n\n".join(
                [
                    f"这场如果要先抓一个底层判断，我更愿意从结构强弱下手。按现有信息看，{verdict}不是情绪化判断。",
                    f"{knowledge_text} 这些背景并不直接决定比分，但能解释为什么一边更容易把比赛拉回自己熟悉的轨道。",
                    f"{form_text} 近期状态再叠上这种长期强弱差，比赛控制权更可能落向准备更完整的一边。",
                    f"{odds_text} 市场没有把这场完全写死，但也没有回避双方底层差异。",
                ]
            )
            title = f"{match.home_team}vs{match.away_team}：这场先别看热闹，先看底层强弱"
            return GeneratedContent(platform=Platform.WECHAT, title=title, content=content)

        if angle_id == "form_window":
            content = "\n\n".join(
                [
                    f"如果只从最近这段比赛感觉入手，{verdict}依然是更自然的读法，因为两队近况并不在一个斜率上。",
                    f"{form_text} 走势当然不会机械换算成比分，但足够说明谁更接近自己想要的比赛形状。",
                    f"{odds_text} 赔率层面的指向没有脱离这条走势线，说明外界也在沿着同一个窗口理解比赛。",
                    f"{knowledge_text} 所以这场不一定会打成一边倒，但方向判断没必要故作中性。",
                ]
            )
            title = f"{match.home_team}vs{match.away_team}：最近这几场，已经把比赛方向写出来了"
            return GeneratedContent(platform=Platform.WECHAT, title=title, content=content)

        if style is StyleSelection.MEDIA_COMMENTARY:
            content = "\n\n".join(
                [
                    f"这场我还是偏向{verdict}，但更重要的是，比赛节奏看起来更像会被一边先拿住。",
                    f"{form_text} 把近期走势放在一起看，能明显感觉到一边更稳，另一边的波动更难藏住。",
                    f"{odds_text} 市场不会代替判断，但它至少把双方现在的预期关系说得足够直白。",
                    f"{knowledge_text} 这些补充放在一起时，{verdict}并不是一句空泛表态。",
                ]
            )
            title = f"{match.home_team}vs{match.away_team}：节奏感已经把这场的方向说透了"
            return GeneratedContent(platform=Platform.WECHAT, title=title, content=content)

        if style is StyleSelection.OLD_HAND:
            content = "\n\n".join(
                [
                    f"这种比赛先看底子，我还是偏{verdict}。真到场上，谁更稳、谁少犯错，通常比谁喊得响更关键。",
                    f"{form_text} 最近这段走势已经把不少问题摊开了：一边更像能把比赛拿住，另一边更容易被节奏带着走。",
                    f"再看市场，{odds_text}。数字不神秘，但也不该装作没看见。",
                    f"{knowledge_text} 这些背景拼到一起，方向其实不难下，难的是别把话说满。",
                ]
            )
            title = f"{match.home_team}vs{match.away_team}：这种球，先看谁的底子更硬"
            return GeneratedContent(platform=Platform.WECHAT, title=title, content=content)

        content = "\n\n".join(
            [
                f"{match.home_team}和{match.away_team}这场，不需要绕很大圈子，当前更顺的方向还是{verdict}。",
                f"{form_text} 走势当然不会直接换算成比分，但足够说明谁更像状态在线的一边。",
                f"{odds_text} 市场不会替你下结论，但它会把强弱预期摆在桌面上。",
                f"{knowledge_text} 这些补充线索不能替代事实，却能让方向判断更稳一些。",
            ]
        )
        title = f"{match.home_team}vs{match.away_team}：先看走势，再看方向"
        return GeneratedContent(platform=Platform.WECHAT, title=title, content=content)

    @staticmethod
    def _fallback_xhs(match: MatchInfo) -> GeneratedContent:
        verdict = AutoFootballPipeline._verdict(match)
        knowledge = match.knowledge_briefs[0] if match.knowledge_briefs else "外部补充信息有限"
        content = (
            f"{match.home_team}打{match.away_team}这场，我先把判断摆出来：{verdict}。\n\n"
            f"主队近况{'/'.join(match.home_recent_form) or '一般'}，客队近况{'/'.join(match.away_recent_form) or '一般'}，"
            "如果你还觉得这就是纯五五开，那可能真的把比赛看得太表面了。"
            "排名、节奏和伤停都会影响比赛走向，不是只看名气就够。\n\n"
            f"补充背景里还有一个点：{knowledge}。"
            f"我个人更偏向{verdict}，但肯定会有人不服。评论区直接说，你站哪边？"
        )
        return GeneratedContent(
            platform=Platform.XIAOHONGSHU,
            title=f"{match.home_team}vs{match.away_team}，这场你真觉得没有倾向？",
            content=content,
        )

    @staticmethod
    def _fallback_xhs_result(match: MatchInfo) -> GeneratedContent:
        score = f"{match.home_score if match.home_score is not None else '-'}:{match.away_score if match.away_score is not None else '-'}"
        content = (
            f"{match.home_team}vs{match.away_team}这场已经打完，最终比分 {score}。\n\n"
            "真正值得聊的不是比分本身，而是这场结果会不会把外界对两队的判断继续拉开。"
            f"从现有信息看，{'；'.join(match.knowledge_briefs[:2]) if match.knowledge_briefs else '这场球的赛果本身已经足够有讨论度。'}\n\n"
            "如果你只看赛果，会觉得就是一场普通比赛；但如果你把它放进近期走势里看，味道就完全不一样了。你觉得这场算爆点，还是只是强弱关系被重新确认？"
        )
        return GeneratedContent(
            platform=Platform.XIAOHONGSHU,
            mode=ContentMode.RESULT_FLASH,
            title=f"{match.home_team}vs{match.away_team}赛果出来了，这场你服吗",
            content=content,
        )

    @staticmethod
    def _fallback_xhs_hot_recap(match: MatchInfo) -> GeneratedContent:
        score = f"{match.home_score if match.home_score is not None else '-'}:{match.away_score if match.away_score is not None else '-'}"
        content = (
            f"{match.home_team}vs{match.away_team}这场，赛后还能继续聊，原因真不只是比分 {score}。\n\n"
            "很多比赛打完就结束了，但有些球会继续发酵，因为它会把球队状态、外界认知和下一轮预期一起带起来。"
            f"{'；'.join(match.knowledge_briefs[:2]) if match.knowledge_briefs else '这场就是那种典型会持续有讨论度的比赛。'}\n\n"
            "所以问题来了，这场是偶然，还是趋势？评论区直接说。"
        )
        return GeneratedContent(
            platform=Platform.XIAOHONGSHU,
            mode=ContentMode.HOT_RECAP,
            title=f"{match.home_team}vs{match.away_team}，这场为什么还在持续发酵",
            content=content,
        )

    @staticmethod
    def _normalize_content(content: str) -> str:
        parts = [part.strip() for part in content.replace("\r\n", "\n").split("\n") if part.strip()]
        return "\n\n".join(parts)

    @staticmethod
    def _section_rules_for_match(match: MatchInfo) -> dict[str, str]:
        merged_rules = (match.merged_context or {}).get("section_rules")
        if isinstance(merged_rules, dict) and merged_rules:
            return merged_rules
        competition_context = ((match.merged_context or {}).get("fact_pack") or {}).get("competition_context") or {}
        sections = competition_context.get("sections")
        if isinstance(sections, dict) and sections:
            return sections
        return {
            "background": "skip" if match.home_rank is None and match.away_rank is None else "include",
            "form": "skip" if not match.home_recent_form and not match.away_recent_form else "include",
            "availability": "skip" if not match.injuries and not match.external_missing_players and not match.external_availability_summary else "include",
            "market": "skip" if not match.odds else "include",
        }

    @staticmethod
    def _sanitize_title(title: str) -> str:
        return " ".join(title.replace("\r", " ").replace("\n", " ").split())

    @staticmethod
    def _length_ok(content: str, minimum: int, maximum: int) -> bool:
        length = len(content.strip())
        return minimum <= length <= maximum

    @staticmethod
    def _truncate_content(content: str, maximum: int) -> str:
        normalized = AutoFootballPipeline._normalize_content(content)
        if len(normalized) <= maximum:
            return normalized
        paragraphs = [item for item in normalized.split("\n\n") if item.strip()]
        kept: list[str] = []
        current_length = 0
        for paragraph in paragraphs:
            separator = 2 if kept else 0
            if current_length + separator + len(paragraph) <= maximum:
                kept.append(paragraph)
                current_length += separator + len(paragraph)
                continue
            remaining = maximum - current_length - separator
            if remaining > 12:
                shortened = paragraph[:remaining].rstrip("，、；： ")
                if shortened and shortened[-1] not in "。！？":
                    shortened = f"{shortened}。"
                kept.append(shortened)
            break
        return "\n\n".join(kept).strip()

    @staticmethod
    def _format_odds_text(odds: dict[str, Any] | None) -> str:
        if not odds:
            return "暂无明确赔率"
        bookmakers = odds.get("bookmakers") if isinstance(odds, dict) else None
        if bookmakers:
            for bookmaker in bookmakers:
                bets = bookmaker.get("bets") or []
                for bet in bets:
                    values = bet.get("values") or []
                    parts = [f"{item.get('value')} {item.get('odd')}" for item in values[:3] if item.get("odd")]
                    if parts:
                        return " | ".join(parts)
        if isinstance(odds, dict) and "eu" in odds:
            immediate = (odds.get("eu") or {}).get("immediate") or {}
            parts = []
            if immediate.get("win"):
                parts.append(f"主胜 {immediate['win']}")
            if immediate.get("draw"):
                parts.append(f"平 {immediate['draw']}")
            if immediate.get("fail"):
                parts.append(f"客胜 {immediate['fail']}")
            if parts:
                return " | ".join(parts)
        return "暂无明确赔率"

    @staticmethod
    def _verdict(match: MatchInfo) -> str:
        if match.home_rank and match.away_rank:
            return f"{match.home_team}不败" if match.home_rank <= match.away_rank else f"{match.away_team}不败"
        if match.home_elo and match.away_elo:
            return f"{match.home_team}不败" if match.home_elo >= match.away_elo else f"{match.away_team}不败"
        return "主队略占优"

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        try:
            return int(value) if value is not None and value != "" else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _expand_wechat_longform(content: str, match: MatchInfo, *, angle_spec=None) -> str:
        base = AutoFootballPipeline._normalize_content(content)
        if len(base) >= WECHAT_MIN_LENGTH:
            return AutoFootballPipeline._truncate_content(base, WECHAT_MAX_LENGTH)

        angle_payload = angle_spec.model_dump(mode="json") if hasattr(angle_spec, "model_dump") else dict(angle_spec or {})
        angle_id = str(angle_payload.get("angle_id") or "")
        knowledge = AutoFootballPipeline._reader_safe_knowledge_summary(match)
        odds_text = AutoFootballPipeline._format_odds_text(match.odds)
        ranking_summary = AutoFootballPipeline._reader_safe_ranking_summary(match)
        form_summary = match.form_summary or (
            f"{match.home_team}近况 {'/'.join(match.home_recent_form) or '信息有限'}，{match.away_team}近况 {'/'.join(match.away_recent_form) or '信息有限'}。"
        )
        strength_summary = AutoFootballPipeline._reader_safe_strength_summary(match)

        fillers = [
            f"把比赛放到更完整的赛前视角里看，最值得参考的不是一句结论本身，而是这场球为什么会把外界判断不断推向同一边。{form_summary}",
            f"如果你不是长期盯足球数据的人，也可以把这场先理解成一场“谁更容易把比赛带进自己节奏”的对话。赔率层面的公开信号是 {odds_text}，它至少说明这场不是完全没有方向感的五五开。",
            f"从读者视角，赛前稿最有价值的地方，不是把每个数据点逐条堆出来，而是把比赛真正重要的变量讲清楚。像这场更值得抓的，就是强弱结构、比赛压力和近期状态究竟是不是在说同一件事。",
            f"再往深一点看，{strength_summary} 这类背景信息的意义，不在于替你直接预测比分，而在于帮助你判断：哪一边更可能在比赛被拉长以后，依然把执行力和稳定性留住。",
            f"{knowledge} 这些补充如果能够和赛前公开信号彼此印证，那么读者就更容易理解，为什么这场的方向判断不是拍脑袋，而是顺着比赛纹理慢慢收出来的。",
            "真正适合公众号的赛前分析，不该像盘口播报，也不该像数据表格。它更像是在替读者完成一次筛选：把最重要的变量留下，把没必要吓人的术语和噪音删掉，然后给出一个站得住脚的方向判断。",
        ]
        if ranking_summary:
            fillers.insert(1, ranking_summary)
        if angle_id == "market_tension":
            fillers.insert(
                0,
                "如果从市场张力切进去，这场的看点其实很清楚：当外界预期、比赛热度和双方真实执行力没有完全重合时，真正值得讲的不是谁名气更大，而是谁更容易兑现那条价格线背后的预期。",
            )
        elif angle_id == "pressure_line":
            fillers.insert(
                0,
                "如果从比赛压力去理解这场，你会发现很多看似细碎的信息最后都在指向同一个问题：谁更能在场面收紧之后保持完整，谁就更有机会把比赛往自己能承受的轨道上拖。",
            )
        elif angle_id == "strength_snapshot":
            fillers.insert(
                0,
                "如果从底层强弱出发，这场最值得读者抓住的不是某个孤立信号，而是长期实力、近期状态和临场可执行性是否叠成了一条线。只要这三件事是同向的，赛前判断就会比表面上更稳。",
            )
        else:
            fillers.insert(
                0,
                "如果从最近这段走势切进去，这场并不是一场需要故意写得模棱两可的比赛。对普通读者来说，更重要的是看懂：哪些信号只是表层热闹，哪些信号已经足够说明比赛会朝哪边慢慢倾斜。",
            )

        expanded = base
        for paragraph in fillers:
            if len(expanded) >= WECHAT_MIN_LENGTH:
                break
            expanded = f"{expanded}\n\n{paragraph}"
        return AutoFootballPipeline._truncate_content(expanded, WECHAT_MAX_LENGTH)

    @staticmethod
    def _reader_safe_knowledge_summary(match: MatchInfo) -> str:
        cleaned = AutoFootballPipeline._humanize_knowledge_briefs(match.knowledge_briefs)
        if cleaned == "当前外部补充信息有限。":
            return cleaned
        return f"补充背景里还能看到这些更稳定的线索：{cleaned}"

    @staticmethod
    def _reader_safe_strength_summary(match: MatchInfo) -> str:
        if match.home_elo is not None and match.away_elo is not None:
            return (
                f"长期强弱层面，{match.home_team}的基础面通常被看得更高，"
                f"而{match.away_team}想把比赛拉回均势，就更需要靠临场执行和阶段状态去抹平差距。"
            )
        if match.home_rank is not None and match.away_rank is not None:
            return (
                f"从联赛位置看，{match.home_team}和{match.away_team}当前并不在同一层级上，"
                "这种差距未必会直接换算成比分，但往往会影响比赛进入僵持段后的稳定性。"
            )
        return "如果缺少完整的长期强弱数据，就更要把目光放回近期走势、比赛压力和临场执行这些读者更容易理解的变量上。"

    @staticmethod
    def _reader_safe_ranking_summary(match: MatchInfo) -> str:
        if match.standings_summary:
            return f"联赛位置这条线也值得单独拎出来看：{match.standings_summary}"
        if match.home_rank is not None and match.away_rank is not None:
            return (
                f"联赛位置上，{match.home_team}目前第{match.home_rank}，{match.away_team}目前第{match.away_rank}。"
                "这不只是一个静态名次差，更意味着双方在拿分压力、赛季目标和容错空间上并不处于同一层级。"
            )
        return ""

    @staticmethod
    def _should_drop_wechat_paragraph_v2(paragraph: str, match: MatchInfo) -> bool:
        del match
        lowered = paragraph.lower()
        if "待补充" in paragraph:
            return True
        if "[clubelo]" in lowered:
            return True
        if "ranked none" in lowered:
            return True
        if " vs " in paragraph and "待补充" in paragraph:
            return True
        if "none" in lowered and "ranked" in lowered:
            return True
        return False

    @staticmethod
    def _should_drop_wechat_paragraph(paragraph: str, match: MatchInfo) -> bool:
        del match
        lowered = paragraph.lower()
        if "待补充" in paragraph:
            return True
        if "[clubelo]" in lowered:
            return True
        if "ranked none" in lowered:
            return True
        if " vs " in paragraph and "待补充" in paragraph:
            return True
        if "none" in lowered and "ranked" in lowered:
            return True
        return False

    @staticmethod
    def _humanize_knowledge_briefs(briefs: list[str]) -> str:
        cleaned: list[str] = []
        for brief in briefs:
            text = str(brief or "").strip()
            if not text:
                continue
            lowered = text.lower()
            if "[clubelo]" in lowered:
                if "ranked none" in lowered:
                    continue
                text = text.replace("[clubelo]", "").strip()
            if "ranked None" in text:
                continue
            cleaned.append(text)
        return "；".join(cleaned[:3]) if cleaned else "当前外部补充信息有限。"

    @staticmethod
    def _apply_section_rules_to_generated_content(plan: RoutedContentPlan, match: MatchInfo, content: str) -> str:
        if plan.platform is not Platform.WECHAT:
            return content
        section_rules = AutoFootballPipeline._section_rules_for_match(match)
        paragraphs = [item.strip() for item in content.replace("\r\n", "\n").split("\n\n") if item.strip()]
        filtered: list[str] = []
        for paragraph in paragraphs:
            if AutoFootballPipeline._should_drop_wechat_paragraph_v2(paragraph, match):
                continue
            if "双方近期走势大致是" in paragraph and "vs" in paragraph:
                continue
            if section_rules.get("background") == "skip" and any(
                token in paragraph for token in ("当前数据未覆盖", "暂无稳定联赛排名数据", "从排名维度看，两队当前公开的名次信息并不完整")
            ):
                continue
            if section_rules.get("availability") == "skip" and any(
                token in paragraph for token in ("暂无明确伤停信息", "没有足够明确的关键伤停名单", "No confirmed injury list")
            ):
                continue
            if section_rules.get("form") == "skip" and any(
                token in paragraph for token in ("近期走势信息有限", "客队最近五场则是待补充", "主队最近五场打出", "双方近期走势大致是")
            ):
                continue
            if section_rules.get("market") == "skip" and any(
                token in paragraph for token in ("赔率和市场倾向", "信息不足，不做延伸判断", "暂无明确赔率")
            ):
                continue
            filtered.append(paragraph)
        return "\n\n".join(filtered)

    @staticmethod
    def _fallback_wechat_result(match: MatchInfo) -> GeneratedContent:
        score = f"{match.home_score if match.home_score is not None else '-'}:{match.away_score if match.away_score is not None else '-'}"
        knowledge = AutoFootballPipeline._humanize_knowledge_briefs(match.knowledge_briefs)
        paragraphs = [
            f"{match.home_team}对阵{match.away_team}这场比赛已经打完，最终比分是{score}。如果只看比分，这当然是一条赛果；但真正值得写的是，这个结果放回联赛背景和双方近期走势里，到底意味着什么。",
            f"先看比赛本身，{match.fixture_status_text or '比赛已经结束'}，最终胜负已经落定。若结合双方赛前的基础面与近期走势，这场球并不是一场完全脱离预期的偶发事件，而更像是阶段状态、比赛强度和执行力共同作用后的自然结果。",
            f"从内容角度，赛后快评最重要的不是复述比分，而是解释结果背后的趋势。{match.home_team}与{match.away_team}在排名、近期表现和整体稳定性上的差异，会继续影响接下来几轮的舆论和市场判断。",
            f"再补一层背景信息：{knowledge}",
            f"所以这场球最值得记住的，不只是最终谁赢谁输，而是它进一步放大了双方当前所处的状态差异。对后续内容运营来说，这样的比赛很适合继续延展做热点复盘或趋势跟踪。",
        ]
        content = AutoFootballPipeline._apply_section_rules_to_generated_content(
            RoutedContentPlan(match_id=match.match_id, platform=Platform.WECHAT, mode=ContentMode.RESULT_FLASH, account_id="wechat-main", score=0, priority=0, reason="fallback"),
            match,
            "\n\n".join(paragraphs),
        )
        return GeneratedContent(
            platform=Platform.WECHAT,
            mode=ContentMode.RESULT_FLASH,
            title=f"{match.home_team}vs{match.away_team}赛果出炉：比分背后更值得看",
            content=AutoFootballPipeline._truncate_content(content, WECHAT_MAX_LENGTH),
        )

    @staticmethod
    def _fallback_wechat_hot_recap(match: MatchInfo) -> GeneratedContent:
        score = f"{match.home_score if match.home_score is not None else '-'}:{match.away_score if match.away_score is not None else '-'}"
        form_text = None
        if match.home_recent_form and match.away_recent_form:
            form_text = f"{'/'.join(match.home_recent_form)} vs {'/'.join(match.away_recent_form)}"
        knowledge = AutoFootballPipeline._humanize_knowledge_briefs(match.knowledge_briefs)
        paragraphs = [
            f"{match.home_team}和{match.away_team}这场比赛之所以还能继续做复盘，不只是因为最终比分{score}，更因为这类对决往往会把双方目前的真实状态放大给所有人看。",
        ]
        if form_text:
            paragraphs.append(
                f"如果把比赛放在更长一点的窗口里看，双方近期走势大致是 {form_text}。这意味着，这场球不是孤立事件，而是近期趋势在一场焦点比赛里的集中呈现。"
            )
        paragraphs.extend(
            [
                "热门复盘的价值，在于把一场球从“结果”提升到“故事”。为什么这场比赛值得继续被讨论？因为它可能影响后续排名走势、舆论热度，甚至下一轮同类比赛的预期方向。",
                f"从现有补充信息看，{knowledge}",
                "这也是为什么热点复盘不需要追求秒级时效，只要在赛后的一段窗口内把结果、背景和趋势讲清楚，它就仍然是一篇有价值的内容。",
            ]
        )
        content = AutoFootballPipeline._apply_section_rules_to_generated_content(
            RoutedContentPlan(match_id=match.match_id, platform=Platform.WECHAT, mode=ContentMode.HOT_RECAP, account_id="wechat-main", score=0, priority=0, reason="fallback"),
            match,
            "\n\n".join(paragraphs),
        )
        return GeneratedContent(
            platform=Platform.WECHAT,
            mode=ContentMode.HOT_RECAP,
            title=f"{match.home_team}vs{match.away_team}复盘：这场球为什么还能继续发酵",
            content=AutoFootballPipeline._truncate_content(content, WECHAT_MAX_LENGTH),
        )
