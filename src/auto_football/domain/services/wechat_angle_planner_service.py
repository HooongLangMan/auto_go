from __future__ import annotations

from auto_football.schemas import EditorialBrief, FactPack, WechatAngleSpec


class WechatAnglePlannerService:
    def build(self, pack: FactPack, brief: EditorialBrief) -> list[WechatAngleSpec]:
        specs: list[WechatAngleSpec] = []

        pressure_hint = self._pressure_hint(pack, brief)
        market_hint = self._market_hint(pack, brief)
        strength_hint = self._strength_hint(pack, brief)
        form_hint = self._form_hint(pack, brief)

        specs.append(
            WechatAngleSpec(
                angle_id="pressure_line",
                angle_label="pressure_line",
                opening_instruction="Open with the match pressure and which team is more likely to carry it cleanly.",
                body_instruction=f"Center the analysis on pressure, match rhythm, and why that matters here. {pressure_hint}",
                title_instruction="Write a title about pressure, rhythm, or who has to absorb the harder emotional load. Avoid generic trend wording.",
            )
        )
        specs.append(
            WechatAngleSpec(
                angle_id="market_tension",
                angle_label="market_tension",
                opening_instruction="Open with the market line, but write it like a columnist rather than a betting sheet.",
                body_instruction=f"Explain how odds, expectation, and matchup tension meet in this fixture. {market_hint}",
                title_instruction="Write a title about price, expectation, or the line the market is setting. Avoid direct tip-sheet phrasing.",
            )
        )
        specs.append(
            WechatAngleSpec(
                angle_id="strength_snapshot",
                angle_label="strength_snapshot",
                opening_instruction="Open with why the strength gap or structural edge matters before kickoff.",
                body_instruction=f"Lean on strength snapshot, long-term profile, and how the stronger side can impose the match. {strength_hint}",
                title_instruction="Write a title about the hidden edge, structural advantage, or who is more likely to dictate the match.",
            )
        )
        specs.append(
            WechatAngleSpec(
                angle_id="form_window",
                angle_label="form_window",
                opening_instruction="Open with recent form as a live signal, not as a stats dump.",
                body_instruction=f"Use recent form to explain current game-state likelihood and where momentum could swing. {form_hint}",
                title_instruction="Write a title about recent form, current momentum, or the shape the last few matches have created.",
            )
        )
        return specs

    @staticmethod
    def _pressure_hint(pack: FactPack, brief: EditorialBrief) -> str:
        hook = brief.primary_angle or ""
        if hook:
            return f"Use this as the pressure spine: {hook}"
        return "Anchor the piece in who faces the harder emotional burden once the match gets tense."

    @staticmethod
    def _market_hint(pack: FactPack, brief: EditorialBrief) -> str:
        summary = str((pack.market_signals or {}).get("summary") or "").strip()
        if summary:
            return f"Use the market summary as one of the core signals: {summary}"
        return "If market data is thin, explain expectation without pretending certainty."

    @staticmethod
    def _strength_hint(pack: FactPack, brief: EditorialBrief) -> str:
        snapshot = str((pack.knowledge_signals or {}).get("strength_snapshot") or "").strip()
        if snapshot:
            return f"Use the strength snapshot directly where helpful: {snapshot}"
        return "If long-term strength is unclear, shift the strength angle to structural control and cleaner execution."

    @staticmethod
    def _form_hint(pack: FactPack, brief: EditorialBrief) -> str:
        summary = str((pack.form_signals or {}).get("summary") or "").strip()
        if summary:
            return f"Treat the recent-form read as a live window, not a checklist: {summary}"
        return "Keep the form angle grounded in momentum and current match sharpness."
