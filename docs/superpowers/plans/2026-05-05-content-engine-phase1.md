# Content Engine Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first phase of the new content engine so match articles use richer facts, route through bounded styles and outlines, generate multiple candidates, and persist ranked review-ready outputs for human selection.

**Architecture:** Keep the current match enrichment pipeline intact, but replace the direct `MatchInfo -> prompt/fallback` content path with a staged content engine: `FactPack -> EditorialBrief -> StyleRouter -> OutlinePlanner -> Writer -> Validator -> CandidateRanker`. Persist the top-ranked draft as the review default while storing alternate candidates and editorial metadata for later selection.

**Tech Stack:** Python 3.12+, Pydantic v2, Typer, SQLAlchemy, pytest, existing `auto_football` pipeline/services/DB layers.

---

## Planned File Structure

### Create

- `src/auto_football/domain/services/fact_pack_service.py`
  - Build `FactPack` from enriched `MatchInfo` and route plan context.
- `src/auto_football/domain/services/editorial_brief_service.py`
  - Convert `FactPack` into an article planning brief with public-language rules.
- `src/auto_football/domain/services/style_router_service.py`
  - Choose bounded style from match/platform/readiness signals and recent usage.
- `src/auto_football/domain/services/outline_planner_service.py`
  - Choose bounded outline skeleton with anti-repetition constraints.
- `src/auto_football/domain/services/content_validation_service.py`
  - Score candidate drafts for fact coverage, gap handling, platform fit, and repetition.
- `src/auto_football/domain/services/candidate_ranking_service.py`
  - Sort and select generated candidates based on validation outputs.
- `tests/test_content_engine_schemas.py`
  - Cover new editorial schemas and metadata behavior.
- `tests/test_fact_pack_service.py`
  - Cover fact extraction, readiness scoring, and plain-language signals.
- `tests/test_editorial_brief_services.py`
  - Cover editorial brief, style routing, and outline routing.
- `tests/test_content_validation_service.py`
  - Cover candidate validation and ranking rules.
- `tests/test_content_pipeline_phase1.py`
  - Cover end-to-end staged content generation and candidate persistence.

### Modify

- `src/auto_football/schemas.py`
  - Add editorial schemas, enums, and metadata fields on `GeneratedContent`.
- `src/auto_football/clients.py`
  - Replace direct platform prompt entrypoint with planned candidate writer entrypoint.
- `src/auto_football/pipeline.py`
  - Wire in new staged content engine and batch anti-repetition state.
- `src/auto_football/domain/services/content_generation_service.py`
  - Generate, validate, rank, and persist candidate pools.
- `src/auto_football/db.py`
  - Save and query editorial metadata for ranked candidates.
- `src/auto_football/infra/db/models.py`
  - Add candidate and editorial metadata columns.
- `src/auto_football/infra/db/migrations.py`
  - Backfill or add new content columns safely.
- `src/auto_football/infra/db/repositories.py`
  - Persist alternate candidates and select the default review candidate.
- `src/auto_football/infra/db/preview_queries.py`
  - Expose candidate rank and editorial metadata in preview payloads.

### Existing Files to Reference While Implementing

- `src/auto_football/pipeline.py`
- `src/auto_football/structured_data.py`
- `src/auto_football/knowledge.py`
- `src/auto_football/clients.py`
- `tests/test_stage0_smoke_baseline.py`
- `tests/test_db_content_storage.py`

### Repository Note

This workspace is currently not a git repository. Every checkpoint step below uses a conditional commit command so the work can still proceed cleanly now and will start committing automatically if the project is moved into a git repo later.

## Task 1: Add Editorial Schemas and Content Metadata

**Files:**
- Create: `tests/test_content_engine_schemas.py`
- Modify: `src/auto_football/schemas.py`

- [ ] **Step 1: Write the failing test**

```python
from auto_football.schemas import (
    ContentReadiness,
    EditorialBrief,
    FactBlockConfidence,
    FactGap,
    FactPack,
    GeneratedContent,
    OutlineSelection,
    Platform,
    StyleSelection,
)


def test_generated_content_supports_editorial_metadata() -> None:
    fact_pack = FactPack(
        match_id=1001,
        platform=Platform.WECHAT,
        mode="pre_match",
        readiness=ContentReadiness.HIGH,
        competition_context={"summary": "Title race pressure"},
        form_signals={"summary": "Home stronger in recent form"},
        availability_signals={},
        market_signals={},
        historical_signals={},
        knowledge_signals={},
        narrative_hooks=["table pressure"],
        data_gaps=[FactGap(field="injuries", severity="medium", message="No confirmed injury list")],
        confidence=FactBlockConfidence(overall=0.82, block_scores={"form_signals": 0.9}),
    )
    brief = EditorialBrief(
        platform=Platform.WECHAT,
        mode="pre_match",
        audience_level="mainstream",
        stance="balanced",
        primary_angle="table pressure",
        secondary_angles=["home form"],
        core_claim="Home side is less likely to lose",
        supporting_evidence=["Recent form stronger", "Ranking edge"],
        discussion_hook="Do you trust the market lean?",
        prohibited_moves=["Do not invent lineup certainty"],
        plain_language_guidance=["Translate Elo as long-term strength background"],
    )
    content = GeneratedContent(
        match_id=1001,
        platform=Platform.WECHAT,
        title="Test",
        content="Body",
        editorial_style=StyleSelection.ANALYST,
        editorial_outline=OutlineSelection.VERDICT_FIRST,
        content_readiness=ContentReadiness.HIGH,
        candidate_rank=1,
        candidate_group="group-1001",
        candidate_count=3,
        quality_summary="High fact coverage",
        editorial_metadata={
            "fact_pack": fact_pack.model_dump(mode="json"),
            "brief": brief.model_dump(mode="json"),
        },
    )

    assert content.editorial_style is StyleSelection.ANALYST
    assert content.editorial_outline is OutlineSelection.VERDICT_FIRST
    assert content.candidate_rank == 1
    assert content.editorial_metadata["brief"]["primary_angle"] == "table pressure"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_content_engine_schemas.py::test_generated_content_supports_editorial_metadata -v
```

Expected: FAIL with import or attribute errors for missing editorial schema types and `GeneratedContent` fields.

- [ ] **Step 3: Write minimal implementation**

```python
from enum import StrEnum


class ContentReadiness(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    REVIEW_HEAVY = "review_heavy"


class StyleSelection(StrEnum):
    ANALYST = "analyst"
    MEDIA_COMMENTARY = "media_commentary"
    OLD_HAND = "old_hand"
    CALM_QUICKTAKE = "calm_quicktake"


class OutlineSelection(StrEnum):
    VERDICT_FIRST = "verdict_first"
    CONTROVERSY_FIRST = "controversy_first"
    TREND_BREAKDOWN = "trend_breakdown"
    RESULT_BACKTRACE = "result_backtrace"
    CAUTIOUS_GAP_AWARE = "cautious_gap_aware"


class FactGap(BaseModel):
    field: str
    severity: str
    message: str


class FactBlockConfidence(BaseModel):
    overall: float = 0.0
    block_scores: dict[str, float] = Field(default_factory=dict)


class FactPack(BaseModel):
    match_id: int
    platform: Platform
    mode: str
    readiness: ContentReadiness
    competition_context: dict[str, Any] = Field(default_factory=dict)
    form_signals: dict[str, Any] = Field(default_factory=dict)
    availability_signals: dict[str, Any] = Field(default_factory=dict)
    market_signals: dict[str, Any] = Field(default_factory=dict)
    historical_signals: dict[str, Any] = Field(default_factory=dict)
    knowledge_signals: dict[str, Any] = Field(default_factory=dict)
    narrative_hooks: list[str] = Field(default_factory=list)
    data_gaps: list[FactGap] = Field(default_factory=list)
    confidence: FactBlockConfidence = Field(default_factory=FactBlockConfidence)


class EditorialBrief(BaseModel):
    platform: Platform
    mode: str
    audience_level: str
    stance: str
    primary_angle: str
    secondary_angles: list[str] = Field(default_factory=list)
    core_claim: str
    supporting_evidence: list[str] = Field(default_factory=list)
    discussion_hook: str = ""
    prohibited_moves: list[str] = Field(default_factory=list)
    plain_language_guidance: list[str] = Field(default_factory=list)


class GeneratedContent(BaseModel):
    ...
    editorial_style: StyleSelection | None = None
    editorial_outline: OutlineSelection | None = None
    content_readiness: ContentReadiness | None = None
    candidate_rank: int | None = None
    candidate_group: str | None = None
    candidate_count: int = 1
    quality_summary: str | None = None
    editorial_metadata: dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
pytest tests/test_content_engine_schemas.py::test_generated_content_supports_editorial_metadata -v
```

Expected: PASS

- [ ] **Step 5: Checkpoint**

Run:

```powershell
if (git rev-parse --is-inside-work-tree 2>$null) {
  git add tests/test_content_engine_schemas.py src/auto_football/schemas.py
  git commit -m "feat: add editorial content schemas"
} else {
  Write-Output "SKIP: workspace is not a git repo"
}
```

Expected: commit created in a git repo, otherwise `SKIP: workspace is not a git repo`

## Task 2: Build FactPack and Readiness Scoring

**Files:**
- Create: `src/auto_football/domain/services/fact_pack_service.py`
- Create: `tests/test_fact_pack_service.py`
- Modify: `src/auto_football/domain/services/__init__.py`

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime, timezone

from auto_football.domain.services.fact_pack_service import FactPackService
from auto_football.schemas import ContentMode, MatchInfo, Platform, RoutedContentPlan


def test_fact_pack_marks_low_readiness_when_key_blocks_are_missing() -> None:
    match = MatchInfo(
        match_id=2001,
        league="Premier League",
        match_time=datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc),
        home_team="Liverpool",
        away_team="Arsenal",
        home_recent_form=[],
        away_recent_form=[],
        injuries=None,
        odds=None,
        knowledge_briefs=[],
    )
    plan = RoutedContentPlan(
        match_id=2001,
        platform=Platform.WECHAT,
        mode=ContentMode.PRE_MATCH,
        account_id="wechat-main",
        score=99,
        priority=99,
        reason="test",
    )

    pack = FactPackService().build(match, plan)

    assert pack.readiness.value == "low"
    assert any(gap.field == "form_signals" for gap in pack.data_gaps)
    assert "mainstream" in pack.knowledge_signals["language_goal"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_fact_pack_service.py::test_fact_pack_marks_low_readiness_when_key_blocks_are_missing -v
```

Expected: FAIL because `FactPackService` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
from auto_football.schemas import ContentReadiness, FactBlockConfidence, FactGap, FactPack


class FactPackService:
    def build(self, match: MatchInfo, plan: RoutedContentPlan) -> FactPack:
        form_summary = {
            "home_form": list(match.home_recent_form),
            "away_form": list(match.away_recent_form),
            "summary": match.form_summary or "",
        }
        competition_context = {
            "summary": match.standings_summary or "",
            "league": match.league,
        }
        availability_signals = {
            "injuries": list(match.injuries or []),
            "summary": "No confirmed injury list" if not match.injuries else "Confirmed injury notes available",
        }
        market_signals = {
            "odds": match.odds or {},
            "summary": "No market signal available" if not match.odds else "Market signal available",
        }
        knowledge_signals = {
            "briefs": list(match.knowledge_briefs),
            "language_goal": "Write for mainstream readers and translate specialist terms",
        }
        gaps: list[FactGap] = []
        if not match.home_recent_form or not match.away_recent_form:
            gaps.append(FactGap(field="form_signals", severity="high", message="Recent form is incomplete"))
        if not match.odds:
            gaps.append(FactGap(field="market_signals", severity="medium", message="Odds are unavailable"))
        if not match.injuries:
            gaps.append(FactGap(field="availability_signals", severity="medium", message="Injury notes are unavailable"))

        readiness = ContentReadiness.HIGH
        if len(gaps) >= 3:
            readiness = ContentReadiness.LOW
        elif gaps:
            readiness = ContentReadiness.MEDIUM

        return FactPack(
            match_id=match.match_id,
            platform=plan.platform,
            mode=plan.mode.value,
            readiness=readiness,
            competition_context=competition_context,
            form_signals=form_summary,
            availability_signals=availability_signals,
            market_signals=market_signals,
            historical_signals={},
            knowledge_signals=knowledge_signals,
            narrative_hooks=self._hooks(match, readiness),
            data_gaps=gaps,
            confidence=FactBlockConfidence(
                overall=0.45 if readiness is ContentReadiness.LOW else 0.7,
                block_scores={
                    "competition_context": 0.7 if competition_context["summary"] else 0.35,
                    "form_signals": 0.9 if match.home_recent_form and match.away_recent_form else 0.1,
                },
            ),
        )

    def _hooks(self, match: MatchInfo, readiness: ContentReadiness) -> list[str]:
        hooks = [f"{match.home_team} vs {match.away_team}"]
        if match.home_rank and match.away_rank:
            hooks.append("table pressure")
        if readiness is ContentReadiness.LOW:
            hooks.append("caution due to thin inputs")
        return hooks
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
pytest tests/test_fact_pack_service.py::test_fact_pack_marks_low_readiness_when_key_blocks_are_missing -v
```

Expected: PASS

- [ ] **Step 5: Checkpoint**

Run:

```powershell
if (git rev-parse --is-inside-work-tree 2>$null) {
  git add tests/test_fact_pack_service.py src/auto_football/domain/services/fact_pack_service.py src/auto_football/domain/services/__init__.py
  git commit -m "feat: add fact pack service"
} else {
  Write-Output "SKIP: workspace is not a git repo"
}
```

Expected: commit created in a git repo, otherwise `SKIP: workspace is not a git repo`

## Task 3: Add EditorialBrief, Style Routing, and Outline Routing

**Files:**
- Create: `src/auto_football/domain/services/editorial_brief_service.py`
- Create: `src/auto_football/domain/services/style_router_service.py`
- Create: `src/auto_football/domain/services/outline_planner_service.py`
- Create: `tests/test_editorial_brief_services.py`

- [ ] **Step 1: Write the failing test**

```python
from auto_football.domain.services.editorial_brief_service import EditorialBriefService
from auto_football.domain.services.outline_planner_service import OutlinePlannerService
from auto_football.domain.services.style_router_service import StyleRouterService
from auto_football.schemas import ContentReadiness, FactBlockConfidence, FactPack, OutlineSelection, Platform, StyleSelection


def test_low_readiness_xhs_routes_to_cautious_quicktake_plan() -> None:
    pack = FactPack(
        match_id=3001,
        platform=Platform.XIAOHONGSHU,
        mode="pre_match",
        readiness=ContentReadiness.LOW,
        competition_context={"summary": ""},
        form_signals={"summary": ""},
        availability_signals={},
        market_signals={},
        historical_signals={},
        knowledge_signals={"language_goal": "Write for mainstream readers"},
        narrative_hooks=["caution due to thin inputs"],
        data_gaps=[],
        confidence=FactBlockConfidence(overall=0.35, block_scores={}),
    )

    brief = EditorialBriefService().build(pack)
    style = StyleRouterService().choose(pack, brief, recent_styles=[StyleSelection.ANALYST])
    outline = OutlinePlannerService().choose(pack, brief, style, recent_pairs=[(StyleSelection.ANALYST, OutlineSelection.VERDICT_FIRST)])

    assert brief.stance == "cautious"
    assert style is StyleSelection.CALM_QUICKTAKE
    assert outline is OutlineSelection.CAUTIOUS_GAP_AWARE
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_editorial_brief_services.py::test_low_readiness_xhs_routes_to_cautious_quicktake_plan -v
```

Expected: FAIL because the new services do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
class EditorialBriefService:
    def build(self, pack: FactPack) -> EditorialBrief:
        stance = "cautious" if pack.readiness in {ContentReadiness.LOW, ContentReadiness.REVIEW_HEAVY} else "balanced"
        primary_angle = pack.narrative_hooks[0] if pack.narrative_hooks else "match context"
        return EditorialBrief(
            platform=pack.platform,
            mode=pack.mode,
            audience_level="mainstream",
            stance=stance,
            primary_angle=primary_angle,
            secondary_angles=pack.narrative_hooks[1:3],
            core_claim="Stay cautious and explain only what the facts support" if stance == "cautious" else "Lead with the strongest supported judgment",
            supporting_evidence=[pack.competition_context.get("summary", ""), pack.form_signals.get("summary", "")],
            discussion_hook="Which side do you trust more from the public signal?" if pack.platform is Platform.XIAOHONGSHU else "",
            prohibited_moves=[gap.message for gap in pack.data_gaps],
            plain_language_guidance=[pack.knowledge_signals.get("language_goal", "Use plain language")],
        )


class StyleRouterService:
    def choose(self, pack: FactPack, brief: EditorialBrief, recent_styles: list[StyleSelection]) -> StyleSelection:
        if pack.platform is Platform.XIAOHONGSHU and pack.readiness is ContentReadiness.LOW:
            return StyleSelection.CALM_QUICKTAKE
        if "table pressure" in pack.narrative_hooks and StyleSelection.ANALYST not in recent_styles:
            return StyleSelection.ANALYST
        return StyleSelection.MEDIA_COMMENTARY


class OutlinePlannerService:
    def choose(
        self,
        pack: FactPack,
        brief: EditorialBrief,
        style: StyleSelection,
        recent_pairs: list[tuple[StyleSelection, OutlineSelection]],
    ) -> OutlineSelection:
        if brief.stance == "cautious":
            return OutlineSelection.CAUTIOUS_GAP_AWARE
        pair = (style, OutlineSelection.VERDICT_FIRST)
        if pair not in recent_pairs:
            return OutlineSelection.VERDICT_FIRST
        if pack.mode == "result_flash":
            return OutlineSelection.RESULT_BACKTRACE
        return OutlineSelection.TREND_BREAKDOWN
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
pytest tests/test_editorial_brief_services.py::test_low_readiness_xhs_routes_to_cautious_quicktake_plan -v
```

Expected: PASS

- [ ] **Step 5: Checkpoint**

Run:

```powershell
if (git rev-parse --is-inside-work-tree 2>$null) {
  git add tests/test_editorial_brief_services.py src/auto_football/domain/services/editorial_brief_service.py src/auto_football/domain/services/style_router_service.py src/auto_football/domain/services/outline_planner_service.py
  git commit -m "feat: add editorial planning services"
} else {
  Write-Output "SKIP: workspace is not a git repo"
}
```

Expected: commit created in a git repo, otherwise `SKIP: workspace is not a git repo`

## Task 4: Refactor the Writer Contract for Planned Candidate Generation

**Files:**
- Modify: `src/auto_football/clients.py`
- Create: `tests/test_content_client_contract.py`

- [ ] **Step 1: Write the failing test**

```python
from auto_football.clients import ChatCompletionClient
from auto_football.schemas import ContentReadiness, EditorialBrief, FactBlockConfidence, FactPack, OutlineSelection, Platform, StyleSelection


def test_writer_prompt_uses_fact_pack_brief_style_and_outline() -> None:
    client = ChatCompletionClient.__new__(ChatCompletionClient)
    pack = FactPack(
        match_id=4001,
        platform=Platform.WECHAT,
        mode="pre_match",
        readiness=ContentReadiness.HIGH,
        competition_context={"summary": "Home side chasing title"},
        form_signals={"summary": "Home form WWWDW, away form LDLWD"},
        availability_signals={"summary": "Away side missing a starting defender"},
        market_signals={"summary": "Home win shortest"},
        historical_signals={},
        knowledge_signals={"language_goal": "Translate specialist terms to mainstream language"},
        narrative_hooks=["table pressure"],
        data_gaps=[],
        confidence=FactBlockConfidence(overall=0.9, block_scores={}),
    )
    brief = EditorialBrief(
        platform=Platform.WECHAT,
        mode="pre_match",
        audience_level="mainstream",
        stance="balanced",
        primary_angle="table pressure",
        secondary_angles=[],
        core_claim="Home side is less likely to lose",
        supporting_evidence=["Home stronger recent form", "Ranking edge"],
        discussion_hook="",
        prohibited_moves=[],
        plain_language_guidance=["Do not mention Elo without explaining it"],
    )

    system_prompt, user_prompt, max_tokens = client._build_candidate_prompt(
        pack=pack,
        brief=brief,
        style=StyleSelection.ANALYST,
        outline=OutlineSelection.VERDICT_FIRST,
    )

    assert "table pressure" in user_prompt
    assert "Do not mention Elo without explaining it" in user_prompt
    assert "Style: analyst" in user_prompt
    assert "Outline: verdict_first" in user_prompt
    assert max_tokens > 1000
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_content_client_contract.py::test_writer_prompt_uses_fact_pack_brief_style_and_outline -v
```

Expected: FAIL because `_build_candidate_prompt` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
class ChatCompletionClient:
    ...
    def _build_candidate_prompt(
        self,
        *,
        pack: FactPack,
        brief: EditorialBrief,
        style: StyleSelection,
        outline: OutlineSelection,
    ) -> tuple[str, str, int]:
        system_prompt = (
            "You are a football content writer for mainstream audiences. "
            "Use only supported facts. Interpret when evidence exists. "
            "Translate specialist concepts into plain language."
        )
        user_prompt = (
            f"Platform: {pack.platform.value}\n"
            f"Mode: {pack.mode}\n"
            f"Style: {style.value}\n"
            f"Outline: {outline.value}\n"
            f"Primary angle: {brief.primary_angle}\n"
            f"Core claim: {brief.core_claim}\n"
            f"Supporting evidence: {brief.supporting_evidence}\n"
            f"Plain language guidance: {brief.plain_language_guidance}\n"
            f"Competition context: {pack.competition_context}\n"
            f"Form signals: {pack.form_signals}\n"
            f"Availability signals: {pack.availability_signals}\n"
            f"Market signals: {pack.market_signals}\n"
            f"Narrative hooks: {pack.narrative_hooks}\n"
            f"Data gaps: {[gap.model_dump(mode='json') for gap in pack.data_gaps]}\n"
            "Return valid JSON with title and content."
        )
        max_tokens = 1800 if pack.platform is Platform.WECHAT else 900
        return system_prompt, user_prompt, max_tokens
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
pytest tests/test_content_client_contract.py::test_writer_prompt_uses_fact_pack_brief_style_and_outline -v
```

Expected: PASS

- [ ] **Step 5: Checkpoint**

Run:

```powershell
if (git rev-parse --is-inside-work-tree 2>$null) {
  git add tests/test_content_client_contract.py src/auto_football/clients.py
  git commit -m "feat: refactor content writer prompt contract"
} else {
  Write-Output "SKIP: workspace is not a git repo"
}
```

Expected: commit created in a git repo, otherwise `SKIP: workspace is not a git repo`

## Task 5: Add Candidate Validation and Ranking

**Files:**
- Create: `src/auto_football/domain/services/content_validation_service.py`
- Create: `src/auto_football/domain/services/candidate_ranking_service.py`
- Create: `tests/test_content_validation_service.py`

- [ ] **Step 1: Write the failing test**

```python
from auto_football.domain.services.candidate_ranking_service import CandidateRankingService
from auto_football.domain.services.content_validation_service import ContentValidationService
from auto_football.schemas import CandidateEvaluation, ContentReadiness, FactBlockConfidence, FactPack, GeneratedContent, Platform, StyleSelection


def test_validator_penalizes_jargon_and_picks_more_readable_candidate() -> None:
    pack = FactPack(
        match_id=5001,
        platform=Platform.XIAOHONGSHU,
        mode="pre_match",
        readiness=ContentReadiness.MEDIUM,
        competition_context={"summary": "Mid-table pressure"},
        form_signals={"summary": "Home form stronger"},
        availability_signals={},
        market_signals={},
        historical_signals={},
        knowledge_signals={"language_goal": "Use mainstream language"},
        narrative_hooks=["home trend stronger"],
        data_gaps=[],
        confidence=FactBlockConfidence(overall=0.7, block_scores={}),
    )
    validator = ContentValidationService()
    ranker = CandidateRankingService()

    jargon = GeneratedContent(match_id=5001, platform=Platform.XIAOHONGSHU, title="A", content="This Elo edge and expected-goals style signal is obvious.")
    readable = GeneratedContent(match_id=5001, platform=Platform.XIAOHONGSHU, title="B", content="Home side has looked steadier recently and that makes the public lean easier to understand.")

    jargon_eval = validator.evaluate(jargon, pack=pack, brief_stance="balanced", recent_openings=[])
    readable_eval = validator.evaluate(readable, pack=pack, brief_stance="balanced", recent_openings=[])
    ordered = ranker.rank([(jargon, jargon_eval), (readable, readable_eval)])

    assert jargon_eval.plain_language_score < readable_eval.plain_language_score
    assert ordered[0][0].title == "B"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_content_validation_service.py::test_validator_penalizes_jargon_and_picks_more_readable_candidate -v
```

Expected: FAIL because validator and ranker services do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
class ContentValidationService:
    JARGON_MARKERS = {"elo", "expected-goals", "xg"}

    def evaluate(
        self,
        content: GeneratedContent,
        *,
        pack: FactPack,
        brief_stance: str,
        recent_openings: list[str],
    ) -> CandidateEvaluation:
        body = content.content.lower()
        plain_language_score = 1.0
        if any(marker in body for marker in self.JARGON_MARKERS):
            plain_language_score -= 0.4
        fact_coverage_score = 0.4
        if pack.form_signals.get("summary") and "steadier" in body or "form" in body:
            fact_coverage_score += 0.3
        repetition_penalty = 0.2 if any(content.content[:40] == opening[:40] for opening in recent_openings) else 0.0
        overall_score = fact_coverage_score + plain_language_score - repetition_penalty
        return CandidateEvaluation(
            fact_coverage_score=fact_coverage_score,
            plain_language_score=plain_language_score,
            platform_fit_score=0.8 if pack.platform is Platform.XIAOHONGSHU and len(content.content) <= 500 else 0.6,
            repetition_penalty_score=repetition_penalty,
            overall_score=overall_score,
            review_summary="Readable mainstream angle" if plain_language_score >= 1.0 else "Needs plainer language",
            hard_fail=False,
        )


class CandidateRankingService:
    def rank(
        self,
        pairs: list[tuple[GeneratedContent, CandidateEvaluation]],
    ) -> list[tuple[GeneratedContent, CandidateEvaluation]]:
        return sorted(
            pairs,
            key=lambda item: (
                item[1].hard_fail,
                -item[1].overall_score,
                -item[1].fact_coverage_score,
                -item[1].plain_language_score,
            ),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
pytest tests/test_content_validation_service.py::test_validator_penalizes_jargon_and_picks_more_readable_candidate -v
```

Expected: PASS

- [ ] **Step 5: Checkpoint**

Run:

```powershell
if (git rev-parse --is-inside-work-tree 2>$null) {
  git add tests/test_content_validation_service.py src/auto_football/domain/services/content_validation_service.py src/auto_football/domain/services/candidate_ranking_service.py
  git commit -m "feat: add content candidate validation and ranking"
} else {
  Write-Output "SKIP: workspace is not a git repo"
}
```

Expected: commit created in a git repo, otherwise `SKIP: workspace is not a git repo`

## Task 6: Integrate the New Content Engine into the Pipeline

**Files:**
- Modify: `src/auto_football/domain/services/content_generation_service.py`
- Modify: `src/auto_football/pipeline.py`
- Create: `tests/test_content_pipeline_phase1.py`

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime, timezone

from auto_football.pipeline import AutoFootballPipeline
from auto_football.config import Settings
from auto_football.schemas import ContentMode, MatchInfo, Platform, RoutedContentPlan


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
        ("top", 0.95),
        ("backup", 0.6),
    ]

    contents = pipeline.content_service.generate([plan], {6001: match})

    assert len(contents) == 1
    assert contents[0].title == "top"
    assert contents[0].candidate_rank == 1
    assert contents[0].candidate_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_content_pipeline_phase1.py::test_pipeline_content_generation_selects_ranked_top_candidate -v
```

Expected: FAIL because `ContentGenerationService` does not yet support candidate pools.

- [ ] **Step 3: Write minimal implementation**

```python
class ContentGenerationService:
    def __init__(self, db, build_candidate_pool) -> None:
        self.db = db
        self.build_candidate_pool = build_candidate_pool

    def generate(self, content_plans, match_data) -> list[GeneratedContent]:
        contents: list[GeneratedContent] = []
        for plan in content_plans:
            match = match_data.get(plan.match_id)
            if match is None:
                continue
            candidates = self.build_candidate_pool(plan, match)
            if not candidates:
                continue
            top_content: GeneratedContent | None = None
            for rank, (content, score) in enumerate(candidates, start=1):
                content.match_id = match.match_id
                content.mode = plan.mode
                content.account_id = plan.account_id
                content.candidate_rank = rank
                content.candidate_count = len(candidates)
                content.quality_summary = f"score={score:.2f}"
                content.status = ContentStatus.READY_TO_PUBLISH if rank == 1 else ContentStatus.DRAFTED
                self.db.save_content(content)
                if rank == 1:
                    top_content = content
            if top_content is not None:
                contents.append(top_content)
        return contents
```

Update pipeline wiring:

```python
self.content_service = ContentGenerationService(self.db, self._build_candidate_pool)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
pytest tests/test_content_pipeline_phase1.py::test_pipeline_content_generation_selects_ranked_top_candidate -v
```

Expected: PASS

- [ ] **Step 5: Checkpoint**

Run:

```powershell
if (git rev-parse --is-inside-work-tree 2>$null) {
  git add tests/test_content_pipeline_phase1.py src/auto_football/domain/services/content_generation_service.py src/auto_football/pipeline.py
  git commit -m "feat: integrate staged content engine candidate flow"
} else {
  Write-Output "SKIP: workspace is not a git repo"
}
```

Expected: commit created in a git repo, otherwise `SKIP: workspace is not a git repo`

## Task 7: Persist Candidate Metadata and Expose Review Alternates

**Files:**
- Modify: `src/auto_football/infra/db/models.py`
- Modify: `src/auto_football/infra/db/migrations.py`
- Modify: `src/auto_football/infra/db/repositories.py`
- Modify: `src/auto_football/infra/db/preview_queries.py`
- Modify: `src/auto_football/db.py`
- Modify: `tests/test_db_content_storage.py`

- [ ] **Step 1: Write the failing test**

```python
def test_database_preserves_ranked_alternate_candidates_for_same_platform_and_mode(tmp_path) -> None:
    db_path = tmp_path / "candidate_rank.db"
    settings = Settings(DATABASE_URL=f"sqlite+pysqlite:///{db_path.as_posix()}")
    db = Database(settings)
    db.init_db()

    top = GeneratedContent(
        match_id=7001,
        platform=Platform.WECHAT,
        mode=ContentMode.PRE_MATCH,
        account_id="wechat-main",
        status=ContentStatus.READY_TO_PUBLISH,
        title="Top candidate",
        content="Top body",
        candidate_rank=1,
        candidate_count=2,
        editorial_style=StyleSelection.ANALYST,
        editorial_outline=OutlineSelection.VERDICT_FIRST,
    )
    backup = GeneratedContent(
        match_id=7001,
        platform=Platform.WECHAT,
        mode=ContentMode.PRE_MATCH,
        account_id="wechat-main",
        status=ContentStatus.DRAFTED,
        title="Backup candidate",
        content="Backup body",
        candidate_rank=2,
        candidate_count=2,
        editorial_style=StyleSelection.MEDIA_COMMENTARY,
        editorial_outline=OutlineSelection.TREND_BREAKDOWN,
    )

    db.save_content(top)
    db.save_content(backup)
    bundle = db.get_match_bundle(7001)

    assert bundle["contents"]["wechat"].title == "Top candidate"
    assert bundle["content_candidates"]["wechat"][0].candidate_rank == 1
    assert bundle["content_candidates"]["wechat"][1].candidate_rank == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
pytest tests/test_db_content_storage.py::test_database_preserves_ranked_alternate_candidates_for_same_platform_and_mode -v
```

Expected: FAIL because candidate metadata columns and `content_candidates` access do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
class ContentRecord(Base):
    ...
    editorial_style = Column(String, nullable=True)
    editorial_outline = Column(String, nullable=True)
    content_readiness = Column(String, nullable=True)
    candidate_rank = Column(Integer, nullable=True)
    candidate_group = Column(String, nullable=True)
    candidate_count = Column(Integer, nullable=False, server_default="1")
    quality_summary = Column(Text, nullable=True)
    editorial_metadata = Column(Text, nullable=True)
```

Migration helper:

```python
def ensure_content_editorial_columns(engine) -> None:
    _ensure_column(engine, "contents", "editorial_style", "varchar")
    _ensure_column(engine, "contents", "editorial_outline", "varchar")
    _ensure_column(engine, "contents", "content_readiness", "varchar")
    _ensure_column(engine, "contents", "candidate_rank", "integer")
    _ensure_column(engine, "contents", "candidate_group", "varchar")
    _ensure_column(engine, "contents", "candidate_count", "integer default 1")
    _ensure_column(engine, "contents", "quality_summary", "text")
    _ensure_column(engine, "contents", "editorial_metadata", "text")
```

Bundle query shape:

```python
return {
    "match": match_payload,
    "contents": selected_by_platform,
    "content_candidates": candidates_by_platform,
}
```

Selection rule:

```python
selected_by_platform[platform] = sorted(items, key=lambda item: (item.candidate_rank or 999, item.created_at), reverse=False)[0]
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
pytest tests/test_db_content_storage.py::test_database_preserves_ranked_alternate_candidates_for_same_platform_and_mode -v
```

Expected: PASS

- [ ] **Step 5: Checkpoint**

Run:

```powershell
if (git rev-parse --is-inside-work-tree 2>$null) {
  git add src/auto_football/infra/db/models.py src/auto_football/infra/db/migrations.py src/auto_football/infra/db/repositories.py src/auto_football/infra/db/preview_queries.py src/auto_football/db.py tests/test_db_content_storage.py
  git commit -m "feat: persist content candidate metadata"
} else {
  Write-Output "SKIP: workspace is not a git repo"
}
```

Expected: commit created in a git repo, otherwise `SKIP: workspace is not a git repo`

## Task 8: Run End-to-End Verification

**Files:**
- Modify: none unless a verification failure requires a fix
- Test: `tests/test_content_engine_schemas.py`
- Test: `tests/test_fact_pack_service.py`
- Test: `tests/test_editorial_brief_services.py`
- Test: `tests/test_content_client_contract.py`
- Test: `tests/test_content_validation_service.py`
- Test: `tests/test_content_pipeline_phase1.py`
- Test: `tests/test_db_content_storage.py`

- [ ] **Step 1: Run focused new-suite verification**

Run:

```powershell
pytest -q tests/test_content_engine_schemas.py tests/test_fact_pack_service.py tests/test_editorial_brief_services.py tests/test_content_client_contract.py tests/test_content_validation_service.py tests/test_content_pipeline_phase1.py tests/test_db_content_storage.py
```

Expected: all listed tests PASS

- [ ] **Step 2: Run full regression suite**

Run:

```powershell
pytest -q
```

Expected: entire suite PASS, with only known warnings unless new failures appear

- [ ] **Step 3: Checkpoint**

Run:

```powershell
if (git rev-parse --is-inside-work-tree 2>$null) {
  git add .
  git commit -m "test: verify content engine phase 1 regressions"
} else {
  Write-Output "SKIP: workspace is not a git repo"
}
```

Expected: commit created in a git repo, otherwise `SKIP: workspace is not a git repo`

## Self-Review

### Spec coverage

- richer facts: covered by Task 2
- editorial planning: covered by Task 3
- bounded style pool: covered by Task 3
- bounded outlines: covered by Task 3
- writer contract shift: covered by Task 4
- validator and ranked candidates: covered by Task 5
- staged content generation integration: covered by Task 6
- alternate candidate persistence for review: covered by Task 7
- human review flow with top-ranked default plus alternates: covered by Tasks 6 and 7

### Placeholder scan

- no `TBD`
- no `TODO`
- no “write tests later”
- no omitted file paths

### Type consistency

- `ContentReadiness`, `StyleSelection`, and `OutlineSelection` are introduced in Task 1 and referenced consistently later
- `FactPack` and `EditorialBrief` are introduced before they are consumed by routing, writing, and validation steps
- `candidate_rank` and related metadata are introduced in Task 1 and persisted in Task 7

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-05-content-engine-phase1.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
