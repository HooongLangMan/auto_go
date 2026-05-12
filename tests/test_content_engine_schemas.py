from auto_football.schemas import (
    ContentMode,
    ContentReadiness,
    EditorialBrief,
    FactBlockConfidence,
    FactGap,
    FactPack,
    GeneratedContent,
    OutlineSelection,
    Platform,
    StyleSelection,
    VisualBrief,
    VisualBriefSlot,
    VisualImageType,
)


def test_generated_content_supports_editorial_metadata() -> None:
    fact_pack = FactPack(
        match_id=1001,
        platform=Platform.WECHAT,
        mode=ContentMode.PRE_MATCH,
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
        mode=ContentMode.PRE_MATCH,
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
    restored = GeneratedContent.model_validate(content.model_dump(mode="json"))

    assert fact_pack.mode is ContentMode.PRE_MATCH
    assert brief.mode is ContentMode.PRE_MATCH
    assert restored.editorial_style is StyleSelection.ANALYST
    assert restored.editorial_outline is OutlineSelection.VERDICT_FIRST
    assert restored.content_readiness is ContentReadiness.HIGH
    assert restored.candidate_rank == 1
    assert restored.candidate_group == "group-1001"
    assert restored.candidate_count == 3
    assert restored.quality_summary == "High fact coverage"
    assert restored.editorial_metadata["fact_pack"]["mode"] == "pre_match"
    assert restored.editorial_metadata["fact_pack"]["readiness"] == "high"
    assert restored.editorial_metadata["fact_pack"]["confidence"]["block_scores"] == {
        "form_signals": 0.9
    }
    assert restored.editorial_metadata["brief"]["mode"] == "pre_match"
    assert restored.editorial_metadata["brief"]["primary_angle"] == "table pressure"


def test_editorial_models_accept_json_style_mode_strings() -> None:
    fact_pack = FactPack(
        match_id=1001,
        platform=Platform.WECHAT,
        mode="pre_match",
        readiness=ContentReadiness.HIGH,
        confidence=FactBlockConfidence(overall=0.82),
    )
    brief = EditorialBrief(
        platform=Platform.WECHAT,
        mode="pre_match",
        audience_level="mainstream",
        stance="balanced",
        primary_angle="table pressure",
        core_claim="Home side is less likely to lose",
        discussion_hook="Do you trust the market lean?",
    )

    assert fact_pack.mode is ContentMode.PRE_MATCH
    assert brief.mode is ContentMode.PRE_MATCH


def test_visual_brief_round_trips_through_json() -> None:
    brief = VisualBrief(
        platform=Platform.WECHAT,
        slot=VisualBriefSlot.WECHAT_HERO,
        image_type=VisualImageType.AI_ACTION_PHOTO,
        scene_angle="home pressure",
        emotion="tense",
        subject_focus="duel",
        headline_text="",
        supporting_text="",
        data_dependency="low",
        fallback_chain=["ai_action_photo", "fallback_card"],
    )

    restored = VisualBrief.model_validate(brief.model_dump(mode="json"))

    assert restored.slot is VisualBriefSlot.WECHAT_HERO
    assert restored.image_type is VisualImageType.AI_ACTION_PHOTO
    assert restored.fallback_chain == ["ai_action_photo", "fallback_card"]
