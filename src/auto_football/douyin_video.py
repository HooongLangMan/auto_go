from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from auto_football.schemas import (
    DouyinVideoJobRequest,
    DouyinVideoMode,
    DouyinVideoTaskRecord,
    DouyinVideoTaskStatus,
    MatchInfo,
)


@dataclass
class DouyinVideoPlanDecision:
    generate: bool
    skip_reason: str | None = None


class DouyinVideoPlanner:
    def plan(self, match: MatchInfo, mode: DouyinVideoMode) -> DouyinVideoPlanDecision:
        if mode is DouyinVideoMode.PRE_MATCH:
            required_ok = bool(match.home_team and match.away_team and match.match_time and match.league)
            return DouyinVideoPlanDecision(
                generate=required_ok,
                skip_reason=None if required_ok else "missing_required_fields",
            )

        required_ok = (
            bool(match.home_team and match.away_team)
            and match.home_score is not None
            and match.away_score is not None
        )
        return DouyinVideoPlanDecision(
            generate=required_ok,
            skip_reason=None if required_ok else "missing_required_fields",
        )


class DouyinVideoPayloadBuilder:
    def build(self, match: MatchInfo, mode: DouyinVideoMode) -> DouyinVideoJobRequest:
        cards: list[str] = []
        if mode is DouyinVideoMode.PRE_MATCH:
            cards.append(f"{match.home_team}对上{match.away_team}，这场先看比赛风向。")
            cards.append(f"{match.league}，开球时间 {match.match_time.strftime('%m-%d %H:%M')}。")
            if match.standings_summary:
                cards.append(match.standings_summary)
            elif match.home_elo_rank is not None or match.away_elo_rank is not None or match.home_elo is not None or match.away_elo is not None:
                parts = []
                if match.home_elo is not None:
                    parts.append(f"{match.home_team} ClubElo {match.home_elo:.0f}")
                if match.away_elo is not None:
                    parts.append(f"{match.away_team} ClubElo {match.away_elo:.0f}")
                cards.append("背景强弱先看这里：" + "，".join(parts) + "。")
            else:
                cards.append("这场的硬信息不算满，但基础对阵和时间已经够用。")
            if match.form_summary:
                cards.append(match.form_summary)
            elif match.home_recent_form or match.away_recent_form:
                home_form = "/".join(match.home_recent_form) if match.home_recent_form else "暂无"
                away_form = "/".join(match.away_recent_form) if match.away_recent_form else "暂无"
                cards.append(f"近况层面，{match.home_team}是 {home_form}，{match.away_team}是 {away_form}。")
            else:
                cards.append("临场更值得看的，是谁能先把节奏带到自己熟悉的轨道。")
        else:
            cards.append(f"赛果出来了，{match.home_team} {match.home_score}-{match.away_score} {match.away_team}。")
            cards.append(match.fixture_status_text or "这场已经打完。")
            if match.standings_summary:
                cards.append(match.standings_summary)
            else:
                cards.append("比分之外，更关键的是这个结果会不会改变外界判断。")
            if match.form_summary:
                cards.append(match.form_summary)
            else:
                cards.append("如果只看结果你会错过重点，真正值得看的是这场怎么走到这里。")

        cards = [item.strip() for item in cards if item and item.strip()][:6]
        title = cards[0] if cards else f"{match.home_team} vs {match.away_team}"
        text = "\n\n".join(cards)
        return DouyinVideoJobRequest(
            match_id=match.match_id,
            video_mode=mode,
            title=title,
            caption_cards=cards,
            facts={
                "league": match.league,
                "home_team": match.home_team,
                "away_team": match.away_team,
                "match_time": match.match_time.isoformat(),
                "home_score": match.home_score,
                "away_score": match.away_score,
            },
            assets={},
            duration_target_sec=20,
            text=text,
            provider_mode="fixed",
            frame_template="1080x1920/static_default.html",
        )


@dataclass
class ProviderSubmitResult:
    provider_task_id: str
    status: DouyinVideoTaskStatus


@dataclass
class ProviderPollResult:
    status: DouyinVideoTaskStatus
    video_url: str | None = None
    error_message: str | None = None


class VideoProvider(Protocol):
    def submit(self, payload: DouyinVideoJobRequest) -> ProviderSubmitResult:
        ...

    def poll(self, provider_task_id: str) -> ProviderPollResult:
        ...


class FakePixelleClient:
    def __init__(self) -> None:
        self._tasks: dict[str, ProviderPollResult] = {}
        self._counter = 0

    def submit(self, payload: DouyinVideoJobRequest) -> ProviderSubmitResult:
        del payload
        self._counter += 1
        task_id = f"fake-{self._counter}"
        self._tasks[task_id] = ProviderPollResult(status=DouyinVideoTaskStatus.RUNNING)
        return ProviderSubmitResult(provider_task_id=task_id, status=DouyinVideoTaskStatus.QUEUED)

    def poll(self, provider_task_id: str) -> ProviderPollResult:
        return self._tasks[provider_task_id]

    def complete(self, provider_task_id: str, *, video_url: str) -> None:
        self._tasks[provider_task_id] = ProviderPollResult(
            status=DouyinVideoTaskStatus.SUCCEEDED,
            video_url=video_url,
        )


class DatabaseDouyinVideoTaskStore:
    def __init__(self, db) -> None:
        self.db = db

    def save_submitted_task(self, record: DouyinVideoTaskRecord) -> DouyinVideoTaskRecord:
        return self.db.save_douyin_video_task(record)

    def get_task_by_provider_task_id(self, provider_task_id: str) -> DouyinVideoTaskRecord | None:
        return self.db.get_douyin_video_task(provider_task_id)

    def update_task(
        self,
        provider_task_id: str,
        *,
        status,
        video_url=None,
        error_message=None,
    ) -> DouyinVideoTaskRecord:
        return self.db.update_douyin_video_task(
            provider_task_id,
            status=status,
            video_url=video_url,
            error_message=error_message,
        )


class PixelleHttpClient:
    def __init__(self, settings) -> None:
        self.settings = settings

    def submit(self, payload: DouyinVideoJobRequest) -> ProviderSubmitResult:
        request_body = {
            "text": payload.text or "\n".join(payload.caption_cards),
            "mode": payload.provider_mode,
            "title": payload.title,
            "n_scenes": max(1, min(len(payload.caption_cards) or 1, 6)),
            "frame_template": payload.frame_template,
        }
        with httpx.Client() as client:
            response = client.post(
                self.settings.pixelle_base_url.rstrip("/") + self.settings.pixelle_submit_path,
                json=request_body,
                timeout=self.settings.pixelle_timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
        task_id = str(body.get("task_id") or body.get("id") or "")
        if not task_id:
            raise ValueError("Pixelle submit response missing task_id")
        return ProviderSubmitResult(provider_task_id=task_id, status=DouyinVideoTaskStatus.QUEUED)

    def poll(self, provider_task_id: str) -> ProviderPollResult:
        task_path = self.settings.pixelle_task_path_template.format(task_id=provider_task_id)
        with httpx.Client() as client:
            response = client.get(
                self.settings.pixelle_base_url.rstrip("/") + task_path,
                timeout=self.settings.pixelle_timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()

        status_text = str(body.get("status") or "").lower()
        if status_text in {"queued", "pending"}:
            return ProviderPollResult(status=DouyinVideoTaskStatus.QUEUED)
        if status_text in {"running", "processing"}:
            return ProviderPollResult(status=DouyinVideoTaskStatus.RUNNING)
        if status_text in {"succeeded", "success", "completed"}:
            result = body.get("result") or {}
            return ProviderPollResult(
                status=DouyinVideoTaskStatus.SUCCEEDED,
                video_url=result.get("video_url") or body.get("video_url") or body.get("url"),
            )
        if status_text in {"failed", "error", "cancelled"}:
            return ProviderPollResult(
                status=DouyinVideoTaskStatus.RENDER_FAILED,
                error_message=str(body.get("error") or body.get("error_message") or "render_failed"),
            )
        return ProviderPollResult(
            status=DouyinVideoTaskStatus.RENDER_FAILED,
            error_message=str(body.get("error_message") or body.get("error") or "render_failed"),
        )


class DouyinVideoService:
    def __init__(self, *, planner, payload_builder, provider: VideoProvider, task_store) -> None:
        self.planner = planner
        self.payload_builder = payload_builder
        self.provider = provider
        self.task_store = task_store

    def submit(self, match: MatchInfo, mode: DouyinVideoMode) -> DouyinVideoTaskRecord:
        decision = self.planner.plan(match, mode)
        if not decision.generate:
            record = DouyinVideoTaskRecord(
                match_id=match.match_id,
                video_mode=mode,
                status=DouyinVideoTaskStatus.SKIPPED_INSUFFICIENT_DATA,
                error_message=decision.skip_reason,
            )
            return self.task_store.save_submitted_task(record)

        payload = self.payload_builder.build(match, mode)
        submitted = self.provider.submit(payload)
        record = DouyinVideoTaskRecord(
            match_id=match.match_id,
            video_mode=mode,
            provider_task_id=submitted.provider_task_id,
            status=submitted.status,
            payload_snapshot=payload.model_dump(mode="json"),
        )
        return self.task_store.save_submitted_task(record)

    def sync(self, provider_task_id: str) -> DouyinVideoTaskRecord:
        polled = self.provider.poll(provider_task_id)
        return self.task_store.update_task(
            provider_task_id,
            status=polled.status,
            video_url=polled.video_url,
            error_message=polled.error_message,
        )
