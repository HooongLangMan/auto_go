from auto_football.clients import ChatCompletionClient
from auto_football.schemas import (
    AudienceLevel,
    ContentReadiness,
    EditorialBrief,
    EditorialStance,
    FactBlockConfidence,
    FactPack,
    OutlineSelection,
    Platform,
    StyleSelection,
)


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
        historical_signals={"summary": "Home unbeaten in last three meetings"},
        knowledge_signals={"language_goal": "Translate specialist terms to mainstream language"},
        narrative_hooks=["table pressure"],
        data_gaps=[],
        confidence=FactBlockConfidence(overall=0.9, block_scores={"form_signals": 0.92}),
    )
    brief = EditorialBrief(
        platform=Platform.WECHAT,
        mode="pre_match",
        audience_level=AudienceLevel.MAINSTREAM,
        stance=EditorialStance.BALANCED,
        primary_angle="table pressure",
        secondary_angles=["home control in midfield"],
        core_claim="Home side is less likely to lose",
        supporting_evidence=["Home stronger recent form", "Ranking edge"],
        discussion_hook="Does the market lean too hard toward the home side?",
        prohibited_moves=["Do not frame this as a guaranteed win"],
        plain_language_guidance=["Do not mention Elo without explaining it"],
    )

    prompt = client._build_candidate_prompt(
        pack=pack,
        brief=brief,
        style=StyleSelection.ANALYST,
        outline=OutlineSelection.VERDICT_FIRST,
    )
    system_prompt, user_prompt, max_tokens = prompt

    assert prompt.system_prompt == system_prompt
    assert prompt.user_prompt == user_prompt
    assert prompt.max_tokens == max_tokens
    assert "structured editorial brief and fact pack" in system_prompt
    assert "table pressure" in user_prompt
    assert "Do not mention Elo without explaining it" in user_prompt
    assert "Style: analyst" in user_prompt
    assert "Outline: verdict_first" in user_prompt
    assert "Secondary angles:" in user_prompt
    assert "home control in midfield" in user_prompt
    assert "Discussion hook: Does the market lean too hard toward the home side?" in user_prompt
    assert "Prohibited moves:" in user_prompt
    assert "Do not frame this as a guaranteed win" in user_prompt
    assert "Historical signals:" in user_prompt
    assert "Home unbeaten in last three meetings" in user_prompt
    assert "Knowledge signals:" in user_prompt
    assert "Translate specialist terms to mainstream language" in user_prompt
    assert "Confidence:" in user_prompt
    assert '"overall": 0.9' in user_prompt
    assert '"form_signals": 0.92' in user_prompt
    assert max_tokens > 1000
    assert "Avoid meta-writing phrases" in user_prompt


def test_writer_prompt_serializes_datetime_fields_from_fact_pack() -> None:
    from datetime import datetime, timezone

    client = ChatCompletionClient.__new__(ChatCompletionClient)
    pack = FactPack(
        match_id=4002,
        platform=Platform.WECHAT,
        mode="pre_match",
        readiness=ContentReadiness.HIGH,
        competition_context={
            "summary": "Home side chasing title",
            "match_time": datetime(2026, 5, 6, 19, 0, tzinfo=timezone.utc),
        },
        form_signals={"summary": "Home form WWWDW, away form LDLWD"},
        availability_signals={},
        market_signals={},
        historical_signals={},
        knowledge_signals={"language_goal": "Translate specialist terms to mainstream language"},
        narrative_hooks=["table pressure"],
        data_gaps=[],
        confidence=FactBlockConfidence(overall=0.9, block_scores={}),
    )
    brief = EditorialBrief(
        platform=Platform.WECHAT,
        mode="pre_match",
        audience_level=AudienceLevel.MAINSTREAM,
        stance=EditorialStance.BALANCED,
        primary_angle="table pressure",
        secondary_angles=[],
        core_claim="Home side is less likely to lose",
        supporting_evidence=[],
        discussion_hook="",
        prohibited_moves=[],
        plain_language_guidance=["Keep it plain."],
    )

    prompt = client._build_candidate_prompt(
        pack=pack,
        brief=brief,
        style=StyleSelection.ANALYST,
        outline=OutlineSelection.VERDICT_FIRST,
    )

    assert "2026-05-06" in prompt.user_prompt
    assert "+00:00" in prompt.user_prompt
