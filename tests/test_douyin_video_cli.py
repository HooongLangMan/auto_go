from __future__ import annotations

from datetime import datetime, timezone

from typer.testing import CliRunner

from auto_football.schemas import ContentMode, GeneratedContent, MatchInfo, Platform


def test_douyin_video_submit_command_submits_task(monkeypatch) -> None:
    from auto_football.cli import app

    runner = CliRunner()

    class FakeDB:
        def __init__(self, settings):
            pass

        def init_db(self):
            return None

        def get_match_bundle(self, match_id):
            return {
                "match": MatchInfo(
                    match_id=match_id,
                    league="Premier League",
                    match_time=datetime(2026, 5, 12, 20, 0, tzinfo=timezone.utc),
                    home_team="Liverpool",
                    away_team="Arsenal",
                ),
                "contents": {
                    "wechat": GeneratedContent(
                        match_id=match_id,
                        platform=Platform.WECHAT,
                        mode=ContentMode.PRE_MATCH,
                        title="seed",
                        content="seed content",
                    )
                },
            }

    class FakeService:
        def __init__(self, *args, **kwargs):
            pass

        def submit(self, match, mode):
            from auto_football.schemas import DouyinVideoTaskRecord, DouyinVideoTaskStatus

            return DouyinVideoTaskRecord(
                match_id=match.match_id,
                video_mode=mode,
                provider_task_id="task-123",
                status=DouyinVideoTaskStatus.QUEUED,
            )

    monkeypatch.setattr("auto_football.cli.Database", FakeDB)
    monkeypatch.setattr("auto_football.cli.build_douyin_video_service", lambda settings, db: FakeService())

    result = runner.invoke(app, ["douyin-video-submit", "--match-id", "42", "--mode", "pre_match"])

    assert result.exit_code == 0
    assert "task-123" in result.stdout


def test_douyin_video_sync_command_prints_video_url(monkeypatch) -> None:
    from auto_football.cli import app

    runner = CliRunner()

    class FakeDB:
        def __init__(self, settings):
            pass

        def init_db(self):
            return None

    class FakeService:
        def __init__(self, *args, **kwargs):
            pass

        def sync(self, task_id):
            from auto_football.schemas import DouyinVideoMode, DouyinVideoTaskRecord, DouyinVideoTaskStatus

            return DouyinVideoTaskRecord(
                match_id=42,
                video_mode=DouyinVideoMode.PRE_MATCH,
                provider_task_id=task_id,
                status=DouyinVideoTaskStatus.SUCCEEDED,
                video_url="https://video.example/final.mp4",
            )

    monkeypatch.setattr("auto_football.cli.Database", FakeDB)
    monkeypatch.setattr("auto_football.cli.build_douyin_video_service", lambda settings, db: FakeService())

    result = runner.invoke(app, ["douyin-video-sync", "--task-id", "task-123"])

    assert result.exit_code == 0
    assert "final.mp4" in result.stdout
