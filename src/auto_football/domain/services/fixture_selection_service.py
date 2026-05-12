from __future__ import annotations


class FixtureSelectionService:
    def __init__(self, router, db, reference_time_fn) -> None:
        self.router = router
        self.db = db
        self.reference_time_fn = reference_time_fn

    def select(self, *, run_id: int, fixtures: list[dict]):
        plans, decisions = self.router.route(fixtures, reference_time=self.reference_time_fn())
        selected = list(dict.fromkeys(plan.match_id for plan in plans))
        self.db.save_selection_results(run_id, decisions)
        return selected, decisions, plans
