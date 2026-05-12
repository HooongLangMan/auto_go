from __future__ import annotations

from datetime import datetime

from auto_football.schemas import MatchInfo


class MatchEnrichmentService:
    def __init__(
        self,
        *,
        db,
        api_football,
        structured_data,
        knowledge,
        the_sports_db,
        run_date_getter,
        build_match_from_public,
        public_key_fn,
        public_odds_fn,
        public_status_code_fn,
        has_required_slots_fn,
    ) -> None:
        self.db = db
        self.api_football = api_football
        self.structured_data = structured_data
        self.knowledge = knowledge
        self.the_sports_db = the_sports_db
        self.run_date_getter = run_date_getter
        self.build_match_from_public = build_match_from_public
        self.public_key_fn = public_key_fn
        self.public_odds_fn = public_odds_fn
        self.public_status_code_fn = public_status_code_fn
        self.has_required_slots_fn = has_required_slots_fn

    def enrich(self, *, run_id: int, selected_match_ids: list[int], public_daily_matches: list[dict]) -> tuple[dict[int, MatchInfo], dict[int, object]]:
        run_date = self.run_date_getter()
        results: dict[int, MatchInfo] = {}
        merged_contexts: dict[int, object] = {}
        public_lookup = {int(item.get("id")): item for item in public_daily_matches if item.get("id") is not None}
        public_name_lookup = {
            self.public_key_fn(item.get("home_team_name_en"), item.get("away_team_name_en")): item
            for item in public_daily_matches
        }

        for match_id in selected_match_ids:
            detail = self.api_football.get_match_detail(match_id)
            if detail is None:
                public_item = public_lookup.get(match_id)
                if public_item:
                    payload = self.build_match_from_public(public_item)
                    payload = self.structured_data.enrich_match(payload, run_date=run_date)
                    context = self.knowledge.gather(payload, run_date, api_snapshot=public_item)
                    payload = self.knowledge.apply_to_match(payload, context)
                    self.db.upsert_match(payload)
                    self.db.save_source_documents(run_id, match_id, context.crawler_documents)
                    self.db.save_merged_context(run_id, context)
                    results[match_id] = payload
                    merged_contexts[match_id] = context
                continue

            league = detail.get("league", {})
            teams = detail.get("teams", {})
            fixture = detail.get("fixture", {})
            status = fixture.get("status", {})
            season = league.get("season")
            league_id = league.get("id")
            home = teams.get("home", {})
            away = teams.get("away", {})
            home_name = home.get("name", "Unknown")
            away_name = away.get("name", "Unknown")
            public_item = public_name_lookup.get(self.public_key_fn(home_name, away_name))

            home_stats = self.api_football.get_team_stats(home.get("id"), league_id=league_id, season=season) if home.get("id") else None
            away_stats = self.api_football.get_team_stats(away.get("id"), league_id=league_id, season=season) if away.get("id") else None
            injuries = []
            if home.get("id"):
                injuries.extend(self.api_football.get_injuries(home["id"], fixture_id=match_id, league_id=league_id, season=season))
            if away.get("id"):
                injuries.extend(self.api_football.get_injuries(away["id"], fixture_id=match_id, league_id=league_id, season=season))

            home_artwork = self.the_sports_db.get_team_artwork(home_name)
            away_artwork = self.the_sports_db.get_team_artwork(away_name)
            payload = MatchInfo(
                match_id=match_id,
                league=league.get("name", "Unknown"),
                match_time=datetime.fromisoformat(fixture["date"].replace("Z", "+00:00")),
                home_team=home_name,
                away_team=away_name,
                home_rank=home_stats.get("rank") if home_stats else None,
                away_rank=away_stats.get("rank") if away_stats else None,
                home_recent_form=(home_stats or {}).get("form", []),
                away_recent_form=(away_stats or {}).get("form", []),
                injuries=injuries or None,
                odds=self.api_football.get_odds(match_id) or self.public_odds_fn(public_item),
                home_logo_url=(public_item or {}).get("home_team_log") or home_artwork.get("badge") or home_artwork.get("logo"),
                away_logo_url=(public_item or {}).get("away_team_log") or away_artwork.get("badge") or away_artwork.get("logo"),
                competition_logo_url=(public_item or {}).get("competition_logo"),
                theme_color=(public_item or {}).get("primary_color"),
                fixture_status=status.get("short") or self.public_status_code_fn(public_item),
                fixture_status_text=status.get("long") or (public_item or {}).get("status_str") or "状态待确认",
                home_score=(detail.get("goals") or {}).get("home"),
                away_score=(detail.get("goals") or {}).get("away"),
                must_fill=self.has_required_slots_fn(
                    {
                        "home_team": home_name,
                        "away_team": away_name,
                        "match_time": fixture.get("date"),
                        "home_recent_form": (home_stats or {}).get("form"),
                        "away_recent_form": (away_stats or {}).get("form"),
                    }
                ),
            )
            payload = self.structured_data.enrich_match(
                payload,
                run_date=run_date,
                api_home_stats=home_stats,
                api_away_stats=away_stats,
            )
            context = self.knowledge.gather(payload, run_date, api_snapshot=detail)
            payload = self.knowledge.apply_to_match(payload, context)
            self.db.upsert_match(payload)
            self.db.save_source_documents(run_id, match_id, context.crawler_documents)
            self.db.save_merged_context(run_id, context)
            results[match_id] = payload
            merged_contexts[match_id] = context

        return results, merged_contexts
