from auto_football.domain.services.content_validation_service import ContentValidationService
from auto_football.schemas import (
    ContentReadiness,
    EditorialStance,
    FactBlockConfidence,
    FactPack,
    GeneratedContent,
    Platform,
)


def test_validator_penalizes_conclusion_that_conflicts_with_market_lead() -> None:
    pack = FactPack(
        match_id=7601,
        platform=Platform.WECHAT,
        mode="pre_match",
        readiness=ContentReadiness.MEDIUM,
        competition_context={"summary": "Big-six matchup"},
        form_signals={"summary": "Home recent form is poor while away form is incomplete."},
        availability_signals={"summary": "No confirmed injury list is available."},
        market_signals={"summary": "European market snapshot: home 1.80 | draw 3.20 | away 4.50", "odds": {"eu": {"immediate": {"win": "1.80", "draw": "3.20", "fail": "4.50"}}}},
        historical_signals={},
        knowledge_signals={"language_goal": "Write for mainstream readers"},
        narrative_hooks=["home side still priced as favorite"],
        data_gaps=[],
        confidence=FactBlockConfidence(overall=0.7, block_scores={}),
    )

    consistent = GeneratedContent(
        match_id=7601,
        platform=Platform.WECHAT,
        title="一致",
        content="我更倾向主队不败。主胜赔率最低，市场明显更看好主队方向。",
    )
    conflicting = GeneratedContent(
        match_id=7601,
        platform=Platform.WECHAT,
        title="冲突",
        content="我更倾向客队不败。虽然主胜赔率最低，但我还是直接看客队方向。",
    )

    validator = ContentValidationService()
    consistent_eval = validator.evaluate(consistent, pack=pack, brief_stance=EditorialStance.CAUTIOUS, recent_openings=[])
    conflicting_eval = validator.evaluate(conflicting, pack=pack, brief_stance=EditorialStance.CAUTIOUS, recent_openings=[])

    assert conflicting_eval.overall_score < consistent_eval.overall_score
    assert "market_conflict" in conflicting_eval.review_summary
