from __future__ import annotations

from datetime import datetime, timezone

import httpx

from auto_football.config import Settings
from auto_football.db import Database
from auto_football.schemas import DouyinVideoJobRequest, DouyinVideoMode, DouyinVideoTaskStatus, MatchInfo


def test_douyin_video_settings_and_enums_exist() -> None:
    settings = Settings()

    assert settings.pixelle_enabled is False
    assert settings.pixelle_base_url == "http://127.0.0.1:8000"
    assert settings.pixelle_submit_path == "/api/video/generate/async"
    assert settings.pixelle_task_path_template == "/api/tasks/{task_id}"

    assert DouyinVideoMode.PRE_MATCH == "pre_match"
    assert DouyinVideoMode.RESULT_FLASH == "result_flash"
    assert DouyinVideoTaskStatus.QUEUED == "queued"
    assert DouyinVideoTaskStatus.SUCCEEDED == "succeeded"


def _match(**overrides):
    base = MatchInfo(
        match_id=101,
        league="Premier League",
        match_time=datetime(2026, 5, 12, 20, 0, tzinfo=timezone.utc),
        home_team="Liverpool",
        away_team="Arsenal",
    )
    return base.model_copy(update=overrides)


def test_planner_accepts_pre_match_with_minimum_fields() -> None:
    from auto_football.douyin_video import DouyinVideoPlanner

    planner = DouyinVideoPlanner()

    result = planner.plan(_match(), DouyinVideoMode.PRE_MATCH)

    assert result.generate is True
    assert result.skip_reason is None


def test_planner_skips_result_flash_without_score() -> None:
    from auto_football.douyin_video import DouyinVideoPlanner

    planner = DouyinVideoPlanner()

    result = planner.plan(_match(home_score=None, away_score=None), DouyinVideoMode.RESULT_FLASH)

    assert result.generate is False
    assert result.skip_reason == "missing_required_fields"


def test_payload_builder_creates_short_caption_cards_for_pre_match() -> None:
    from auto_football.douyin_video import DouyinVideoPayloadBuilder

    builder = DouyinVideoPayloadBuilder()

    payload = builder.build(
        _match(standings_summary="Liverpool second, Arsenal fourth."),
        DouyinVideoMode.PRE_MATCH,
    )

    assert payload.video_mode == DouyinVideoMode.PRE_MATCH
    assert payload.match_id == 101
    assert payload.duration_target_sec == 20
    assert payload.caption_cards
    assert len(payload.caption_cards) <= 6
    assert payload.assets == {}
    assert payload.text.count("\n\n") == 3


class InMemoryTaskStore:
    def __init__(self):
        self.saved = {}

    def save_submitted_task(self, record):
        key = record.provider_task_id or f"skip-{record.match_id}-{record.video_mode}"
        self.saved[key] = record
        return record

    def get_task_by_provider_task_id(self, provider_task_id):
        return self.saved.get(provider_task_id)

    def update_task(self, provider_task_id, *, status, video_url=None, error_message=None):
        record = self.saved[provider_task_id]
        record.status = status
        record.video_url = video_url
        record.error_message = error_message
        return record


def test_service_submit_creates_queued_task_record() -> None:
    from auto_football.douyin_video import (
        DouyinVideoPayloadBuilder,
        DouyinVideoPlanner,
        DouyinVideoService,
        FakePixelleClient,
    )

    store = InMemoryTaskStore()
    service = DouyinVideoService(
        planner=DouyinVideoPlanner(),
        payload_builder=DouyinVideoPayloadBuilder(),
        provider=FakePixelleClient(),
        task_store=store,
    )

    record = service.submit(_match(), DouyinVideoMode.PRE_MATCH)

    assert record.status == DouyinVideoTaskStatus.QUEUED
    assert record.provider_task_id is not None
    assert record.payload_snapshot["match_id"] == 101


def test_service_sync_updates_finished_video_url() -> None:
    from auto_football.douyin_video import (
        DouyinVideoPayloadBuilder,
        DouyinVideoPlanner,
        DouyinVideoService,
        FakePixelleClient,
    )

    store = InMemoryTaskStore()
    provider = FakePixelleClient()
    service = DouyinVideoService(
        planner=DouyinVideoPlanner(),
        payload_builder=DouyinVideoPayloadBuilder(),
        provider=provider,
        task_store=store,
    )

    submitted = service.submit(_match(home_score=2, away_score=1), DouyinVideoMode.RESULT_FLASH)
    provider.complete(submitted.provider_task_id, video_url="https://video.example/out.mp4")

    synced = service.sync(submitted.provider_task_id)

    assert synced.status == DouyinVideoTaskStatus.SUCCEEDED
    assert synced.video_url == "https://video.example/out.mp4"


def test_database_task_store_round_trips_service_records(tmp_path) -> None:
    from auto_football.douyin_video import (
        DatabaseDouyinVideoTaskStore,
        DouyinVideoPayloadBuilder,
        DouyinVideoPlanner,
        DouyinVideoService,
        FakePixelleClient,
    )

    db_path = tmp_path / "service_store.db"
    db = Database(Settings(DATABASE_URL=f"sqlite+pysqlite:///{db_path.as_posix()}"))
    db.init_db()
    store = DatabaseDouyinVideoTaskStore(db)
    provider = FakePixelleClient()
    service = DouyinVideoService(
        planner=DouyinVideoPlanner(),
        payload_builder=DouyinVideoPayloadBuilder(),
        provider=provider,
        task_store=store,
    )

    submitted = service.submit(_match(), DouyinVideoMode.PRE_MATCH)
    provider.complete(submitted.provider_task_id, video_url="https://video.example/ok.mp4")
    synced = service.sync(submitted.provider_task_id)

    assert synced.status == DouyinVideoTaskStatus.SUCCEEDED
    assert db.get_douyin_video_task(submitted.provider_task_id).video_url == "https://video.example/ok.mp4"


def test_pixelle_http_client_submit_maps_task_id(monkeypatch) -> None:
    from auto_football.douyin_video import PixelleHttpClient

    settings = Settings()
    client = PixelleHttpClient(settings)
    captured = {}

    def fake_post(self, url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"task_id": "pixelle-123"}

        return Response()

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    result = client.submit(
        DouyinVideoJobRequest(
            match_id=1,
            video_mode=DouyinVideoMode.PRE_MATCH,
            title="Title",
            caption_cards=["A", "B"],
            facts={},
            assets={},
            duration_target_sec=20,
        )
    )

    assert result.provider_task_id == "pixelle-123"
    assert result.status == DouyinVideoTaskStatus.QUEUED
    assert captured["url"].endswith("/api/video/generate/async")
    assert captured["json"]["text"] == "A\nB"
    assert captured["json"]["mode"] == "fixed"
    assert captured["json"]["frame_template"] == "1080x1920/static_default.html"


def test_pixelle_http_client_poll_reads_video_url_from_result_payload(monkeypatch) -> None:
    from auto_football.douyin_video import PixelleHttpClient

    settings = Settings()
    client = PixelleHttpClient(settings)

    def fake_get(self, url, timeout):
        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "task_id": "pixelle-123",
                    "status": "completed",
                    "result": {
                        "video_url": "http://localhost:8000/api/files/out/final.mp4",
                    },
                }

        return Response()

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    result = client.poll("pixelle-123")

    assert result.status == DouyinVideoTaskStatus.SUCCEEDED
    assert result.video_url == "http://localhost:8000/api/files/out/final.mp4"
