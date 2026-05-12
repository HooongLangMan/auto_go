# Content Engine Design

Date: 2026-05-05

## Goal

Upgrade the current football content pipeline from a direct template-or-prompt flow into a controllable editorial engine that:

- improves information density using high-value free data sources
- reduces assembly-line sameness through bounded style variation
- keeps articles readable for mainstream audiences rather than only football specialists
- supports different writing goals for WeChat and Xiaohongshu
- produces multiple ranked candidates for human review instead of forcing a single output

This phase is content-only. It does not include cover redesign, insert-image redesign, or full automation of publishing.

## Why This Change

The current pipeline has three weaknesses that directly affect output quality:

1. Match input is often too thin, so the model writes around missing facts.
2. Article structure is too repetitive, so different matches read like the same template.
3. Platform differences are under-modeled, so WeChat and Xiaohongshu outputs diverge mostly by length rather than by intent and reading rhythm.

The design in this document addresses those three weaknesses in order:

1. enrich the fact base
2. introduce editorial decision layers before writing
3. validate and rank multiple candidates for human review

## Scope

### In scope

- expand structured content inputs with selected free or already-integrated data sources
- build a `FactPack` abstraction on top of raw match data
- build an `EditorialBrief` abstraction that decides what the article should emphasize
- add automatic style routing with a bounded style pool
- add outline planning with multiple reusable skeletons
- generate multiple candidates per match/platform/mode
- validate, rank, and store candidate metadata for review
- preserve factual grounding while allowing broader and more readable explanations

### Out of scope

- redesigning image generation or cover generation
- adding AI-generated cover art in this phase
- enabling fully automated publishing
- adding many unstable scraping targets
- perfecting all leagues and all content modes in one iteration

## Product Principles

### 1. Facts first, but not sterile

The system must remain grounded in real data, but it should not become so rigid that it produces empty articles. Facts are the base layer. Interpretation is allowed when it is anchored to facts. Fabrication is not allowed.

### 2. Mainstream readable, not jargon-heavy

The system may use advanced metrics internally, but the final article should translate specialist concepts into plain language. For example, ClubElo can inform long-term strength judgments, but the final text should usually explain it as background strength or long-term stability rather than dropping unexplained jargon.

### 3. Controlled variety beats pure randomness

The system should not write in one voice forever, but it also should not feel chaotic. Variation comes from a limited style pool, rotating outlines, and anti-repetition checks rather than unconstrained randomness.

### 4. Platform intent matters more than character count

WeChat and Xiaohongshu should differ in goal, pacing, and interaction model, not only in length.

### 5. Human review remains the gate

This phase optimizes quality for supervised review. The system should generate better material for selection, not attempt to bypass editorial judgment.

## Data Strategy

This phase should prefer high-value, free, or already-integrated sources that are stable enough to support iterative development.

### Recommended source roles

- `API-Football`: primary match intelligence source
  - fixtures
  - standings
  - injuries
  - odds
  - lineups, where available
  - match statistics, where available
  - pre-match predictions, only as a low-weight signal

- `football-data.org`: structured fallback and verification source
  - competition table
  - schedule
  - team match history

- `TheSportsDB`: lightweight metadata and artwork helper
  - club and competition media
  - basic descriptive metadata where available

- `openfootball` and related open match history:
  - historical trend context
  - recent form cross-checks
  - post-match long-window framing

### First-phase source priorities

The first phase should not chase every possible field. It should prioritize fields that most directly improve article quality:

1. competition context
2. recent form quality
3. injuries and availability
4. odds and market direction
5. matchup background
6. historical context for recap content

### Data gaps policy

Missing data should become explicit editorial input rather than hidden failure. The system should record:

- what is missing
- how important it is
- whether the article should remain assertive or become more cautious

This prevents the current failure mode where thin input still gets forced through the same article pattern.

## Architecture

The content engine should evolve from:

`MatchInfo -> direct prompt or fallback`

to:

`MatchInfo + enrichment -> FactPack -> EditorialBrief -> StyleRouter -> OutlinePlanner -> Writer -> Validator -> CandidateRanker`

## Core Components

### FactPack

`FactPack` is a normalized editorial facts object. It is not a dump of raw JSON. It is a writing-oriented representation of the best available facts for a match.

Suggested fields:

- `match_header`
  - match id
  - league
  - kickoff
  - home team
  - away team
  - fixture status
  - score if finished

- `competition_context`
  - league ranks
  - points or rank bands when available
  - title race, European qualification, relegation, or mid-table context
  - whether this is a key round or pressure match

- `form_signals`
  - recent form for both teams
  - home and away signal when available
  - scoring and conceding tendency
  - streaks

- `availability_signals`
  - injuries
  - suspensions if available
  - lineup confidence
  - missing key role markers

- `market_signals`
  - odds summary
  - market lean
  - whether odds align with table and form
  - whether there is visible disagreement

- `historical_signals`
  - recent head-to-head
  - similar-opponent signal
  - longer trend context for recap modes

- `knowledge_signals`
  - brief external context snippets
  - long-term strength indicators such as ClubElo translated into plain-language interpretation

- `narrative_hooks`
  - 2 to 4 candidate story angles derived from the facts

- `data_gaps`
  - missing critical fields
  - seriousness of each gap

- `confidence`
  - overall readiness score
  - block-level confidence
  - source provenance summary

### Content readiness score

Replace the effective role of `must_fill` with a richer `content_readiness_score`.

Suggested levels:

- `high`
  - enough facts to support a strong analysis article

- `medium`
  - enough facts for a useful article, but some sections should be lighter

- `low`
  - enough to write a short, cautious piece only

- `review_heavy`
  - article may still be generated, but should be clearly marked for closer review

This score should influence style, outline, tone, and whether the article is allowed to sound decisive.

### EditorialBrief

`EditorialBrief` is the article planning layer. It decides what the article is about before drafting begins.

Suggested fields:

- `platform`
- `mode`
- `audience_level`
  - mainstream
  - football-interested but not specialist

- `stance`
  - assertive
  - balanced
  - cautious

- `primary_angle`
  - strongest editorial angle for this piece

- `secondary_angles`
  - backup angles if needed

- `core_claim`
  - the main judgment or takeaway

- `supporting_evidence`
  - ranked fact blocks to cite

- `discussion_hook`
  - especially important for Xiaohongshu

- `prohibited_moves`
  - claims not allowed because data is too weak

- `plain_language_guidance`
  - specialist concepts that must be translated into public-friendly language

### StyleRouter

The router chooses from a bounded pool of mature writing styles. It should be automatic, not manually selected in normal operation.

Initial style pool:

- `analyst`
  - dense, disciplined, evidence-led

- `media_commentary`
  - professional with more narrative flow

- `old_hand`
  - sharper judgment, still evidence-backed

- `calm_quicktake`
  - suitable for fast recaps and short public-facing summaries

Routing inputs:

- platform
- mode
- content readiness score
- match importance
- rivalry or strong-vs-strong signal
- upset or controversy signal
- recent style usage history to avoid repetition

### OutlinePlanner

The planner picks an article skeleton after style selection. Even within one style, structure should vary.

Initial outline pool:

- `verdict_first`
- `controversy_first`
- `trend_breakdown`
- `result_backtrace`
- `cautious_gap_aware`

The planner should avoid reusing the same style and outline pair too frequently for the same date, account, or platform batch.

### Writer

The writer should no longer receive raw `MatchInfo` as the main prompt body. It should receive:

- concise `FactPack`
- `EditorialBrief`
- chosen style
- chosen outline
- platform guidance

This allows the model to focus on execution rather than first discovering what matters.

### Validator

The validator is required in phase one because content quality is the main objective.

Validation layers:

- `fact_coverage`
  - did the article actually use the strongest available facts

- `gap_respect`
  - did the article acknowledge missing information instead of inventing certainty

- `plain_language`
  - did it translate specialist concepts into readable public-facing language

- `platform_fit`
  - is the structure and pace right for WeChat vs Xiaohongshu

- `anti_repetition`
  - does it resemble recent outputs too closely

- `length`
  - character and pacing suitability

### CandidateRanker

The system should generate multiple candidates per match-platform-mode and rank them before review.

Suggested first-phase candidate count:

- WeChat: 2 to 3 candidates
- Xiaohongshu: 2 to 4 candidates

Ranking criteria:

- fact coverage
- readability
- platform fit
- distinctiveness
- repetition penalty
- confidence alignment

The highest-ranked draft becomes the default recommendation. Other candidates remain available for fallback selection.

## Platform Strategy

### WeChat

Writing goal:

- explain the match clearly
- justify the judgment
- preserve structure and reading depth

Characteristics:

- longer body
- stronger section transitions
- better suited for layered explanation
- safe place for richer recap logic
- can later support insert-image placement between sections

### Xiaohongshu

Writing goal:

- establish a readable stance quickly
- surface the most interesting angle fast
- create discussion without sounding empty

Characteristics:

- shorter
- faster hook
- stronger discussion point
- lower tolerance for long setup
- should feel more scroll-native

The system should not simply shorten WeChat output for Xiaohongshu. Each platform should have its own planning and validation rules.

## Factual Grounding Policy

The first version should use a three-layer writing model:

- `hard fact layer`
  - must be true and source-backed

- `interpretation layer`
  - allowed when anchored to the fact layer

- `expression layer`
  - free to vary in voice and rhythm

This preserves credibility without making the article empty.

## Anti-Template Strategy

The system should actively fight the current assembly-line feel with the following rules:

- bounded style pool instead of a single default tone
- bounded outline pool instead of a single section order
- no repeated style-outline combination too frequently within the same batch
- title starter diversity
- opening paragraph diversity
- closing paragraph diversity
- evidence order variation where appropriate

Variation should remain controlled. The goal is “same editorial system, multiple human-feeling outputs,” not randomness for its own sake.

## Candidate Failure Handling

Candidate generation should not assume one-shot success.

Suggested failure handling:

- light failure
  - keep style, swap outline, rewrite

- medium failure
  - change style and outline, rewrite

- heavy failure
  - mark as review-heavy and surface lower-ranked candidate instead

The system should make it cheap to switch to another candidate rather than forcing a total regenerate from scratch for every bad draft.

## Storage and Review Metadata

Store review-useful metadata alongside generated content. Suggested metadata:

- selected style
- selected outline
- content readiness score
- fact coverage score
- repetition penalty score
- platform fit score
- candidate rank
- reviewer summary string

This helps the human reviewer decide quickly whether to approve the top candidate or swap to another one.

## Proposed Codebase Changes

### New or expanded concepts

- `FactPack` schema
- `EditorialBrief` schema
- `CandidateEvaluation` schema
- `StyleSelection` enum or typed metadata
- `OutlineSelection` enum or typed metadata

### Likely implementation locations

- `src/auto_football/schemas.py`
  - add new schemas and metadata types

- `src/auto_football/domain/services/`
  - add focused services such as:
    - `fact_pack_service.py`
    - `editorial_brief_service.py`
    - `style_router_service.py`
    - `outline_planner_service.py`
    - `content_validation_service.py`
    - `candidate_ranking_service.py`

- `src/auto_football/clients.py`
  - refactor `ChatCompletionClient` so content generation takes structured editorial inputs rather than only raw match and platform

- `src/auto_football/pipeline.py`
  - replace direct content generation path with the new staged content engine

- `src/auto_football/db.py` and `infra/db/*`
  - persist additional content metadata and candidate information

### Suggested pipeline phase behavior

Within the content phase:

1. build `FactPack`
2. build `EditorialBrief`
3. choose style
4. choose outline
5. generate multiple candidates
6. validate candidates
7. rank candidates
8. store best candidate and metadata

## Testing Strategy

This phase needs stronger content tests than the current repository has.

### Unit tests

- Fact pack assembly from partial and full data
- readiness score assignment
- style routing decisions
- outline planning diversity
- plain-language translation rules
- anti-repetition checks
- candidate ranking behavior

### Prompt contract tests

- verify writer input includes fact pack, brief, style, and outline
- verify platform-specific planning is used

### Regression tests

- low-data match should not produce overconfident copy
- two matches in the same batch should not collapse to near-identical openings
- Xiaohongshu should remain short and hook-first
- WeChat should remain structured and explanatory

### Review-oriented tests

- if top candidate fails validation, next candidate should be available
- candidate metadata should be persisted correctly

## Phase One Delivery Criteria

Phase one is successful if:

- articles contain clearly more usable information than the current version
- same-day outputs no longer feel like one template repeated
- WeChat and Xiaohongshu outputs are visibly different in intent and rhythm
- mainstream readers can understand the content without specialist football jargon
- reviewer can switch among ranked candidates rather than relying on a single draft

## Risks

- too many new data sources can destabilize the system
- too much variation can reduce brand coherence
- too much validation can make generation brittle
- storing too little metadata will weaken the review loop

## Mitigations

- keep first-phase sources selective
- keep style pool small and intentional
- keep validation layered rather than binary-only
- persist explicit candidate diagnostics

## Recommended First Implementation Order

1. introduce `FactPack`
2. introduce `content_readiness_score`
3. introduce `EditorialBrief`
4. add style routing
5. add outline planning
6. refactor writer input contract
7. add validator
8. add multi-candidate ranking and persistence

## Decision Summary

This design intentionally avoids trying to perfect everything at once. It chooses a staged editorial engine because that is the best fit for the actual current pain points:

- insufficient usable facts
- repetitive article shape
- weak platform differentiation

It also preserves the current product reality:

- quality is reviewed by a human
- automation is deferred
- iteration matters more than early perfection
