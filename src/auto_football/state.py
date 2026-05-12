from __future__ import annotations

from typing import TypedDict

from auto_football.schemas import GeneratedContent, MatchInfo, MergedMatchContext, PublishResult, RoutedContentPlan, SelectionDecision


class GraphState(TypedDict):
    run_id: int
    fixtures: list[dict]
    selected_match_ids: list[int]
    selection_results: list[SelectionDecision]
    content_plans: list[RoutedContentPlan]
    match_data: dict[int, MatchInfo]
    merged_contexts: dict[int, MergedMatchContext]
    contents: list[GeneratedContent]
    publish_status: dict[int, dict[str, PublishResult]]
