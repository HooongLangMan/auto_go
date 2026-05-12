from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from auto_football.cache import CacheStore
from auto_football.clients import ClubEloClient, FBrefClient, OpenFootballClient, StatsBombOpenClient, WhoScoredClient
from auto_football.schemas import MatchInfo, MergedMatchContext, SourceDocument


class MultiSourceKnowledgeService:
    def __init__(
        self,
        cache: CacheStore,
        db,
        clubelo: ClubEloClient,
        openfootball: OpenFootballClient,
        statsbomb: StatsBombOpenClient,
        fbref: FBrefClient,
        whoscored: WhoScoredClient,
    ) -> None:
        self.cache = cache
        self.db = db
        self.clubelo = clubelo
        self.openfootball = openfootball
        self.statsbomb = statsbomb
        self.fbref = fbref
        self.whoscored = whoscored

    def gather(self, match: MatchInfo, run_date: date, api_snapshot: dict[str, Any]) -> MergedMatchContext:
        cache_key = self.cache.merged_context_key(match.match_id, run_date)
        cached = self.cache.get_json(cache_key)
        if cached:
            context = MergedMatchContext.model_validate(cached)
            if self._cache_is_usable(context):
                return context

        snapshot = self.db.get_latest_context_snapshot(match.match_id) if self.db is not None else None
        if snapshot:
            context = MergedMatchContext(
                fixture_id=snapshot["fixture_id"],
                api_snapshot=snapshot.get("api_snapshot") or {},
                crawler_documents=[SourceDocument.model_validate(item) for item in snapshot.get("source_documents") or []],
                merged_payload=snapshot.get("merged_payload") or {},
                cache_key=snapshot.get("cache_key"),
            )
            if self._cache_is_usable(context):
                self.cache.set_json(cache_key, context.model_dump(mode="json"), ttl_seconds=self.cache.settings.context_cache_ttl_seconds)
                return context

        crawled_at = datetime.now(timezone.utc)
        docs: list[SourceDocument] = []

        clubelo_rankings = self._get_clubelo_rankings(run_date)
        docs.extend(self.clubelo.build_documents(match.home_team, match.away_team, clubelo_rankings, crawled_at))
        docs.extend(self.openfootball.build_team_documents(match.league, match.home_team, run_date, crawled_at))
        docs.extend(self.openfootball.build_team_documents(match.league, match.away_team, run_date, crawled_at))
        docs.extend(self.statsbomb.build_team_documents(match.home_team, crawled_at))
        docs.extend(self.statsbomb.build_team_documents(match.away_team, crawled_at))
        docs.extend(
            self.fbref.build_match_documents(
                match.league,
                match.home_team,
                match.away_team,
                run_date=run_date,
                crawled_at=crawled_at,
            )
        )
        docs.extend(
            self.whoscored.build_match_documents(
                match.league,
                match.home_team,
                match.away_team,
                run_date=run_date,
                crawled_at=crawled_at,
            )
        )

        merged_payload = self._merge_payload(match, docs)
        context = MergedMatchContext(
            fixture_id=match.match_id,
            api_snapshot=api_snapshot,
            crawler_documents=docs,
            merged_payload=merged_payload,
            cache_key=cache_key,
        )
        self.cache.set_json(cache_key, context.model_dump(mode="json"), ttl_seconds=self.cache.settings.context_cache_ttl_seconds)
        return context

    def apply_to_match(self, match: MatchInfo, context: MergedMatchContext) -> MatchInfo:
        merged = context.merged_payload
        match.home_elo = merged.get("home_elo")
        match.away_elo = merged.get("away_elo")
        match.home_elo_rank = merged.get("home_elo_rank")
        match.away_elo_rank = merged.get("away_elo_rank")
        if not match.home_recent_form:
            match.home_recent_form = merged.get("home_recent_form", [])
        if not match.away_recent_form:
            match.away_recent_form = merged.get("away_recent_form", [])
        match.knowledge_briefs = merged.get("knowledge_briefs", [])
        home_missing = merged.get("home_missing_players", [])
        away_missing = merged.get("away_missing_players", [])
        combined_missing = [*home_missing, *away_missing]
        existing_injuries = list(match.injuries or [])
        deduped_missing = [item for item in combined_missing if item not in existing_injuries]
        if existing_injuries or deduped_missing:
            match.injuries = [*existing_injuries, *deduped_missing]
        match.external_missing_players = combined_missing
        match.external_availability_summary = merged.get("whoscored_availability_summary")
        home_summary = (merged.get("fbref_team_stat_summaries") or {}).get(match.home_team)
        away_summary = (merged.get("fbref_team_stat_summaries") or {}).get(match.away_team)
        match.external_stat_summary = " ".join(part for part in (home_summary, away_summary) if part) or None
        match.source_documents_count = len(context.crawler_documents)
        match.merged_context = merged
        return match

    def _get_clubelo_rankings(self, run_date: date) -> list[dict[str, Any]]:
        key = self.cache.clubelo_key(run_date)
        cached = self.cache.get_json(key)
        if cached:
            return cached
        rankings = self.clubelo.get_rankings(run_date)
        self.cache.set_json(key, rankings, ttl_seconds=self.cache.settings.source_doc_cache_ttl_seconds)
        return rankings

    def _cache_is_usable(self, context: MergedMatchContext) -> bool:
        if self.openfootball.enabled:
            has_openfootball = any(doc.source == "openfootball" for doc in context.crawler_documents)
            merged = context.merged_payload or {}
            if not has_openfootball and not merged.get("home_recent_form") and not merged.get("away_recent_form"):
                return False
        return True

    @staticmethod
    def _merge_payload(match: MatchInfo, docs: list[SourceDocument]) -> dict[str, Any]:
        merged: dict[str, Any] = {
            "home_elo": None,
            "away_elo": None,
            "home_elo_rank": None,
            "away_elo_rank": None,
            "home_recent_form": list(match.home_recent_form),
            "away_recent_form": list(match.away_recent_form),
            "knowledge_briefs": [],
            "home_missing_players": [],
            "away_missing_players": [],
            "whoscored_availability_summary": None,
            "fbref_team_stat_summaries": {},
            "coverage": {
                "sources": {},
                "total_signals": 0,
                "ready": False,
            },
        }
        for doc in docs:
            if doc.source == "clubelo" and doc.team_name == match.home_team:
                merged["home_elo"] = MultiSourceKnowledgeService._safe_float(doc.payload.get("Elo"))
                merged["home_elo_rank"] = MultiSourceKnowledgeService._safe_int(doc.payload.get("Rank"))
            if doc.source == "clubelo" and doc.team_name == match.away_team:
                merged["away_elo"] = MultiSourceKnowledgeService._safe_float(doc.payload.get("Elo"))
                merged["away_elo_rank"] = MultiSourceKnowledgeService._safe_int(doc.payload.get("Rank"))
            if doc.source == "openfootball" and doc.team_name == match.home_team and len(merged["home_recent_form"]) < 5:
                merged["home_recent_form"] = MultiSourceKnowledgeService._derive_form_from_docs(match.home_team, docs)
            if doc.source == "openfootball" and doc.team_name == match.away_team and len(merged["away_recent_form"]) < 5:
                merged["away_recent_form"] = MultiSourceKnowledgeService._derive_form_from_docs(match.away_team, docs)
            if doc.source == "fbref" and doc.source_type == "team_stat_snapshot":
                stat_summary = str((doc.payload or {}).get("summary") or (doc.payload or {}).get("stat_summary") or doc.summary or "").strip()
                if doc.team_name and stat_summary:
                    merged["fbref_team_stat_summaries"][doc.team_name] = stat_summary
            if doc.source == "whoscored":
                payload = doc.payload or {}
                home_missing = list(payload.get("home_missing") or [])
                away_missing = list(payload.get("away_missing") or [])
                if not home_missing and not away_missing and payload.get("player"):
                    player = str(payload.get("player") or "").strip()
                    reason = str(payload.get("reason") or "").strip()
                    status = str(payload.get("status") or "").strip()
                    entry = f"{player}: {reason} ({status})" if reason or status else player
                    team_name = str(payload.get("team") or doc.team_name or "")
                    normalized_team = OpenFootballClient._normalize_name(team_name)
                    if normalized_team == OpenFootballClient._normalize_name(match.home_team):
                        home_missing = [entry]
                    elif normalized_team == OpenFootballClient._normalize_name(match.away_team):
                        away_missing = [entry]
                merged["home_missing_players"] = home_missing
                merged["away_missing_players"] = away_missing
                merged["whoscored_availability_summary"] = payload.get("summary") or doc.summary
            if doc.source == "fbref" and doc.source_type == "site_snapshot":
                continue
            if doc.summary:
                merged["knowledge_briefs"].append(f"[{doc.source}] {doc.summary}")
        merged["knowledge_briefs"] = merged["knowledge_briefs"][:10]
        merged["coverage"] = MultiSourceKnowledgeService._coverage_summary(match, merged, docs)
        return merged

    @staticmethod
    def _coverage_summary(match: MatchInfo, merged: dict[str, Any], docs: list[SourceDocument]) -> dict[str, Any]:
        source_flags: dict[str, dict[str, bool]] = {
            "api_football": {
                "rank": bool(match.home_rank or match.away_rank),
                "form": bool(match.home_recent_form or match.away_recent_form),
                "odds": bool(match.odds),
                "injuries": bool(match.injuries),
            },
            "clubelo": {"elo": bool(merged.get("home_elo") or merged.get("away_elo"))},
            "fbref": {"summary": bool(merged.get("fbref_team_stat_summaries"))},
            "whoscored": {"availability": bool(merged.get("whoscored_availability_summary"))},
            "openfootball": {"form": bool(merged.get("home_recent_form") or merged.get("away_recent_form"))},
        }
        total_signals = sum(1 for group in source_flags.values() for value in group.values() if value)
        return {
            "sources": source_flags,
            "total_signals": total_signals,
            "ready": total_signals >= 3 and (bool(match.home_recent_form or match.away_recent_form) or bool(match.odds)),
        }

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        try:
            return float(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        try:
            return int(float(value)) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _derive_form_from_docs(team_name: str, docs: list[SourceDocument], limit: int = 5) -> list[str]:
        normalized = OpenFootballClient._normalize_name(team_name)
        form: list[str] = []
        for doc in docs:
            if doc.source != "openfootball":
                continue
            payload = doc.payload or {}
            home = payload.get("team1") or payload.get("home") or {}
            away = payload.get("team2") or payload.get("away") or {}
            home_name = home.get("name") if isinstance(home, dict) else str(home)
            away_name = away.get("name") if isinstance(away, dict) else str(away)
            score = payload.get("score") or {}
            home_goals, away_goals = MultiSourceKnowledgeService._extract_openfootball_score(score, payload.get("ft"))
            if home_goals is None or away_goals is None:
                continue
            if OpenFootballClient._team_matches(normalized, str(home_name)):
                form.append("W" if home_goals > away_goals else "D" if home_goals == away_goals else "L")
            elif OpenFootballClient._team_matches(normalized, str(away_name)):
                form.append("W" if away_goals > home_goals else "D" if away_goals == home_goals else "L")
            if len(form) >= limit:
                break
        return form

    @staticmethod
    def _extract_openfootball_score(score: Any, fallback: Any) -> tuple[int | None, int | None]:
        if isinstance(score, dict):
            ft = score.get("ft")
            if isinstance(ft, list) and len(ft) >= 2:
                try:
                    return int(ft[0]), int(ft[1])
                except Exception:
                    return None, None
            if isinstance(ft, str) and "-" in ft:
                try:
                    left, right = ft.split("-", 1)
                    return int(left.strip()), int(right.strip())
                except Exception:
                    return None, None
        if isinstance(fallback, list) and len(fallback) >= 2:
            try:
                return int(fallback[0]), int(fallback[1])
            except Exception:
                return None, None
        if isinstance(fallback, str) and "-" in fallback:
            try:
                left, right = fallback.split("-", 1)
                return int(left.strip()), int(right.strip())
            except Exception:
                return None, None
        return None, None
