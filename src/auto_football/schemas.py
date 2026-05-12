from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Platform(StrEnum):
    WECHAT = "wechat"
    XIAOHONGSHU = "xiaohongshu"
    DOUYIN = "douyin"


class ContentMode(StrEnum):
    PRE_MATCH = "pre_match"
    RESULT_FLASH = "result_flash"
    HOT_RECAP = "hot_recap"


class DouyinVideoMode(StrEnum):
    PRE_MATCH = "pre_match"
    RESULT_FLASH = "result_flash"


class ContentStatus(StrEnum):
    DRAFTED = "drafted"
    READY_TO_PUBLISH = "ready_to_publish"
    PUBLISHED = "published"
    FAILED = "failed"


class VisualImageType(StrEnum):
    REAL_PHOTO = "real_photo"
    AI_ACTION_PHOTO = "ai_action_photo"
    HYBRID_COVER = "hybrid_cover"
    FALLBACK_CARD = "fallback_card"


class VisualBriefSlot(StrEnum):
    WECHAT_HERO = "wechat_hero"
    WECHAT_INLINE = "wechat_inline"
    XHS_COVER = "xhs_cover"


class ContentReadiness(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    REVIEW_HEAVY = "review_heavy"


class AudienceLevel(StrEnum):
    MAINSTREAM = "mainstream"
    INFORMED = "informed"


class EditorialStance(StrEnum):
    CAUTIOUS = "cautious"
    BALANCED = "balanced"


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
    overall: float
    block_scores: dict[str, float] = Field(default_factory=dict)


class FactPack(BaseModel):
    match_id: int
    platform: Platform
    mode: ContentMode
    readiness: ContentReadiness
    competition_context: dict[str, Any] = Field(default_factory=dict)
    form_signals: dict[str, Any] = Field(default_factory=dict)
    availability_signals: dict[str, Any] = Field(default_factory=dict)
    market_signals: dict[str, Any] = Field(default_factory=dict)
    historical_signals: dict[str, Any] = Field(default_factory=dict)
    knowledge_signals: dict[str, Any] = Field(default_factory=dict)
    narrative_hooks: list[str] = Field(default_factory=list)
    data_gaps: list[FactGap] = Field(default_factory=list)
    confidence: FactBlockConfidence


class EditorialBrief(BaseModel):
    platform: Platform
    mode: ContentMode
    audience_level: AudienceLevel
    stance: EditorialStance
    primary_angle: str
    secondary_angles: list[str] = Field(default_factory=list)
    core_claim: str
    supporting_evidence: list[str] = Field(default_factory=list)
    discussion_hook: str
    prohibited_moves: list[str] = Field(default_factory=list)
    plain_language_guidance: list[str] = Field(default_factory=list)


class WechatAngleSpec(BaseModel):
    angle_id: str
    angle_label: str
    opening_instruction: str
    body_instruction: str
    title_instruction: str


class MatchInfo(BaseModel):
    match_id: int
    league: str
    match_time: datetime

    home_team: str
    away_team: str

    home_rank: int | None = None
    away_rank: int | None = None

    home_recent_form: list[str] = Field(default_factory=list)
    away_recent_form: list[str] = Field(default_factory=list)

    injuries: list[str] | None = None
    odds: dict[str, Any] | None = None
    home_logo_url: str | None = None
    away_logo_url: str | None = None
    competition_logo_url: str | None = None
    theme_color: str | None = None
    fixture_status: str | None = None
    fixture_status_text: str | None = None
    home_score: int | None = None
    away_score: int | None = None
    home_elo: float | None = None
    away_elo: float | None = None
    home_elo_rank: int | None = None
    away_elo_rank: int | None = None
    rank_source: str | None = None
    form_source: str | None = None
    standings_summary: str | None = None
    form_summary: str | None = None
    knowledge_briefs: list[str] = Field(default_factory=list)
    source_documents_count: int = 0
    merged_context: dict[str, Any] | None = None
    external_missing_players: list[str] = Field(default_factory=list)
    external_availability_summary: str | None = None
    external_stat_summary: str | None = None

    must_fill: bool = True


class GeneratedContent(BaseModel):
    match_id: int = 0
    platform: Platform
    mode: ContentMode = ContentMode.PRE_MATCH
    account_id: str = "default"
    status: ContentStatus = ContentStatus.DRAFTED
    priority: int = 0
    title: str
    content: str
    images: list[str] = Field(default_factory=list)
    image_prompts: list[str] = Field(default_factory=list)
    remote_images: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    primary_media_path: str | None = None
    tags: list[str] = Field(default_factory=list)
    editorial_style: StyleSelection | None = None
    editorial_outline: OutlineSelection | None = None
    content_readiness: ContentReadiness | None = None
    candidate_rank: int | None = None
    candidate_group: str | None = None
    candidate_count: int = 1
    quality_summary: str | None = None
    editorial_metadata: dict[str, Any] = Field(default_factory=dict)


class VisualBrief(BaseModel):
    platform: Platform
    slot: VisualBriefSlot
    image_type: VisualImageType
    scene_angle: str
    emotion: str
    subject_focus: str
    headline_text: str = ""
    supporting_text: str = ""
    data_dependency: str = "low"
    fallback_chain: list[str] = Field(default_factory=list)


class CandidateEvaluation(BaseModel):
    plain_language_score: float
    fact_coverage_score: float
    platform_fit_score: float
    repetition_penalty: float = 0.0
    overall_score: float
    review_summary: str
    hard_fail: bool = False


class PublishResult(BaseModel):
    platform: Platform
    status: str
    publish_id: str | None = None
    error_message: str | None = None


class DouyinVideoTaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    SUBMIT_FAILED = "submit_failed"
    RENDER_FAILED = "render_failed"
    TIMEOUT = "timeout"
    SKIPPED_INSUFFICIENT_DATA = "skipped_insufficient_data"


class DouyinVideoJobRequest(BaseModel):
    match_id: int
    video_mode: DouyinVideoMode
    title: str
    caption_cards: list[str] = Field(default_factory=list)
    facts: dict[str, Any] = Field(default_factory=dict)
    assets: dict[str, Any] = Field(default_factory=dict)
    duration_target_sec: int = 20
    text: str = ""
    provider_mode: str = "fixed"
    frame_template: str = "1080x1920/static_default.html"


class DouyinVideoTaskRecord(BaseModel):
    match_id: int
    video_mode: DouyinVideoMode
    provider: str = "pixelle"
    provider_task_id: str | None = None
    status: DouyinVideoTaskStatus
    video_url: str | None = None
    error_message: str | None = None
    payload_snapshot: dict[str, Any] = Field(default_factory=dict)


class SourceDocument(BaseModel):
    source: str
    source_type: str = "external"
    team_name: str | None = None
    url: str | None = None
    title: str | None = None
    published_at: datetime | None = None
    crawled_at: datetime | None = None
    summary: str | None = None
    content_text: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class SelectionDecision(BaseModel):
    fixture_id: int
    selected: bool
    score: int
    reason: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContentTarget(BaseModel):
    account_id: str
    platform: Platform
    quota: int = 1
    modes: list[ContentMode] = Field(default_factory=list)


class RoutedContentPlan(BaseModel):
    match_id: int
    platform: Platform
    mode: ContentMode
    account_id: str
    score: int
    priority: int
    reason: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class MergedMatchContext(BaseModel):
    fixture_id: int
    run_id: int | None = None
    api_snapshot: dict[str, Any] = Field(default_factory=dict)
    crawler_documents: list[SourceDocument] = Field(default_factory=list)
    merged_payload: dict[str, Any] = Field(default_factory=dict)
    cache_key: str | None = None
