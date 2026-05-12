from auto_football.domain.services.candidate_ranking_service import CandidateRankingService
from auto_football.domain.services.content_validation_service import ContentValidationService
from auto_football.schemas import (
    CandidateEvaluation,
    ContentReadiness,
    EditorialStance,
    FactBlockConfidence,
    FactPack,
    GeneratedContent,
    Platform,
    StyleSelection,
)


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

    jargon = GeneratedContent(
        match_id=5001,
        platform=Platform.XIAOHONGSHU,
        title="A",
        content="This Elo edge and expected-goals style signal is obvious.",
    )
    readable = GeneratedContent(
        match_id=5001,
        platform=Platform.XIAOHONGSHU,
        title="B",
        content="Home side has looked steadier recently and that makes the public lean easier to understand.",
    )

    jargon_eval = validator.evaluate(
        jargon,
        pack=pack,
        brief_stance=EditorialStance.BALANCED,
        recent_openings=[],
    )
    readable_eval = validator.evaluate(
        readable,
        pack=pack,
        brief_stance=EditorialStance.BALANCED,
        recent_openings=[],
    )
    ordered = ranker.rank([(jargon, jargon_eval), (readable, readable_eval)])

    assert jargon_eval.plain_language_score < readable_eval.plain_language_score
    assert ordered[0][0].title == "B"


def test_validator_marks_empty_content_as_hard_fail() -> None:
    pack = FactPack(
        match_id=5002,
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

    evaluation = ContentValidationService().evaluate(
        GeneratedContent(match_id=5002, platform=Platform.XIAOHONGSHU, title="Empty", content="   "),
        pack=pack,
        brief_stance=EditorialStance.BALANCED,
        recent_openings=[],
    )

    assert evaluation.hard_fail is True
    assert evaluation.overall_score == 0.0


def test_validator_applies_repetition_penalty_for_reused_opening() -> None:
    pack = FactPack(
        match_id=5003,
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

    evaluation = ContentValidationService().evaluate(
        GeneratedContent(
            match_id=5003,
            platform=Platform.XIAOHONGSHU,
            title="Repeat",
            content="Home side has looked steadier recently. The crowd is noticing it.",
        ),
        pack=pack,
        brief_stance=EditorialStance.BALANCED,
        recent_openings=["Home side has looked steadier recently"],
    )

    assert evaluation.repetition_penalty > 0.0


def test_validator_penalizes_template_meta_phrases() -> None:
    pack = FactPack(
        match_id=5004,
        platform=Platform.WECHAT,
        mode="pre_match",
        readiness=ContentReadiness.MEDIUM,
        competition_context={"summary": "Big match pressure"},
        form_signals={"summary": "Home form stronger"},
        availability_signals={},
        market_signals={},
        historical_signals={},
        knowledge_signals={"language_goal": "Use mainstream language"},
        narrative_hooks=["home trend stronger"],
        data_gaps=[],
        confidence=FactBlockConfidence(overall=0.7, block_scores={}),
    )

    templatey = GeneratedContent(
        match_id=5004,
        platform=Platform.WECHAT,
        title="A",
        content="对公众号读者来说，赛前分析最重要的不是绕很多弯，而是先把方向说清楚。",
    )
    natural = GeneratedContent(
        match_id=5004,
        platform=Platform.WECHAT,
        title="B",
        content="先说判断：主队更值得高看，核心原因还是近况和主场强度更硬。",
    )

    validator = ContentValidationService()
    template_eval = validator.evaluate(templatey, pack=pack, brief_stance=EditorialStance.BALANCED, recent_openings=[])
    natural_eval = validator.evaluate(natural, pack=pack, brief_stance=EditorialStance.BALANCED, recent_openings=[])

    assert template_eval.overall_score < natural_eval.overall_score
    assert "meta_phrase" in template_eval.review_summary


def test_opening_line_handles_chinese_and_english_sentence_boundaries() -> None:
    assert ContentValidationService.opening_line("主队更稳。客队波动更大。") == "主队更稳"
    assert ContentValidationService.opening_line("Home side looks steadier. Away side remains volatile.") == "Home side looks steadier"
